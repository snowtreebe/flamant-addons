from odoo import api, fields, models, tools


class FlamantQuotationLine(models.Model):
    """Read-only line-level pipeline view of open quotations.

    Mirrors the structure of flamant.sales.line (Order Intake Lines) but on
    sale.order.line where the order is still in state='sent'. No cost or
    margin is exposed — quotations have no SVL and no confirmed margin.
    """

    _name = 'flamant.quotation.line'
    _description = 'Flamant Quotation Lines (sent sale.order.line)'
    _auto = False
    _order = 'date desc'

    # --- Time dimensions ---
    date = fields.Date(readonly=True)
    year_num = fields.Integer(string='Year', readonly=True)
    month_num = fields.Integer(string='Month', readonly=True)
    weekday_num = fields.Selection(
        [
            ('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'),
            ('4', 'Thursday'), ('5', 'Friday'), ('6', 'Saturday'), ('7', 'Sunday'),
        ],
        string='Weekday',
        readonly=True,
    )

    # --- Channel / country / shop (mirrors flamant.sales.line) ---
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    channel = fields.Selection(
        [
            ('shops',        'Shops'),
            ('ecommerce',    'Online / E-Commerce'),
            ('wholesale',    'Wholesale'),
            ('franchise',    'Franchise'),
            ('flamant_home', 'Flamant@Home'),
            ('outlet',       'Outlet'),
            ('other',        'Other'),
        ],
        readonly=True,
    )
    country_code = fields.Selection(
        [
            ('BE',    'Belgium'),
            ('FR',    'France'),
            ('INT',   'International'),
            ('OTHER', 'Other'),
        ],
        string='Country',
        readonly=True,
    )
    shop_label = fields.Char(readonly=True)
    shop_cluster = fields.Char(readonly=True)
    is_comparable = fields.Boolean(string='Comparable', readonly=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Budget Analytic Account',
        readonly=True,
    )

    # --- Source document ---
    source_ref = fields.Char(string='Reference', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)
    source_doc = fields.Reference(
        selection=[('sale.order', 'Sales Order')],
        string='Document',
        compute='_compute_source_doc',
    )

    # --- Product ---
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_categ_id = fields.Many2one('product.category', string='Category', readonly=True)

    # --- Quantities & money (NO cost / margin) ---
    qty = fields.Float(string='Quantity', readonly=True)
    revenue = fields.Monetary(string='Revenue', readonly=True)

    # --- Quotation context ---
    validity_date = fields.Date(string='Validity', readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)

    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    @api.depends('source_id')
    def _compute_source_doc(self):
        for r in self:
            r.source_doc = f"sale.order,{r.source_id}" if r.source_id else False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY so.date_order, so.team_id, sol.id
                    ) AS id,
                    so.date_order::date                                            AS date,
                    EXTRACT(YEAR  FROM so.date_order)::int                         AS year_num,
                    EXTRACT(MONTH FROM so.date_order)::int                         AS month_num,
                    CASE EXTRACT(DOW FROM so.date_order)::int
                        WHEN 0 THEN '7' ELSE EXTRACT(DOW FROM so.date_order)::text
                    END                                                            AS weekday_num,
                    so.team_id                                                     AS team_id,
                    t.channel                                                      AS channel,
                    CASE
                        WHEN t.channel IN ('ecommerce', 'wholesale') THEN
                            CASE
                                WHEN pc.code = 'BE' THEN 'BE'
                                WHEN pc.code = 'FR' THEN 'FR'
                                WHEN pc.code IS NOT NULL THEN 'INT'
                                ELSE 'OTHER'
                            END
                        ELSE t.country_code
                    END                                                            AS country_code,
                    COALESCE(NULLIF(t.shop_label, ''), t.name->>'en_US')           AS shop_label,
                    COALESCE(NULLIF(t.shop_cluster, ''), t.shop_label,
                             t.name->>'en_US')                                      AS shop_cluster,
                    COALESCE(t.comparable, FALSE)                                  AS is_comparable,
                    t.analytic_account_id                                          AS analytic_account_id,
                    so.name                                                        AS source_ref,
                    so.id                                                          AS source_id,
                    sol.product_id                                                 AS product_id,
                    pt.categ_id                                                    AS product_categ_id,
                    sol.product_uom_qty                                            AS qty,
                    sol.price_subtotal                                             AS revenue,
                    so.validity_date                                               AS validity_date,
                    so.user_id                                                     AS salesperson_id,
                    so.partner_shipping_id                                         AS partner_id,
                    so.company_id                                                  AS company_id,
                    rc.currency_id                                                 AS currency_id
                FROM sale_order_line sol
                JOIN sale_order       so ON so.id = sol.order_id
                JOIN product_product  pp ON pp.id = sol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN crm_team    t  ON t.id  = so.team_id
                LEFT JOIN res_partner p  ON p.id  = so.partner_shipping_id
                LEFT JOIN res_country pc ON pc.id = p.country_id
                LEFT JOIN res_company rc ON rc.id = so.company_id
                WHERE so.state = 'sent'
                  AND so.team_id IS NOT NULL
                  AND COALESCE(sol.is_downpayment, FALSE) = FALSE
                  AND (sol.display_type IS NULL
                       OR sol.display_type NOT IN ('line_section', 'line_note'))
                  AND sol.product_id IS NOT NULL
            )
            """
        )
