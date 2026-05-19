from odoo import api, fields, models, tools


class FlamantQuotation(models.Model):
    """Read-only view of open and cancelled sales quotations.

    Pipeline counterpart to flamant.sales.header: instead of confirmed
    revenue, this surfaces sale.order records that are still in
    quotation stage (draft, sent) or cancelled. Confirmed orders are
    intentionally excluded — those belong in Order Intake.
    """

    _name = 'flamant.quotation'
    _description = 'Flamant Quotations (open + cancelled sale.order)'
    _auto = False
    _order = 'date desc'

    date = fields.Date(string='Date', readonly=True)
    year_num = fields.Integer(string='Year', readonly=True)
    month_num = fields.Integer(string='Month', readonly=True)
    state = fields.Selection(
        [
            ('draft',  'Quotation'),
            ('sent',   'Quotation Sent'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        readonly=True,
    )
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
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
    validity_date = fields.Date(string='Validity', readonly=True)
    amount_untaxed = fields.Monetary(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    source_ref = fields.Char(string='Reference', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)
    source_doc = fields.Reference(
        selection=[('sale.order', 'Sales Order')],
        string='Document',
        compute='_compute_source_doc',
    )

    @api.depends('source_id')
    def _compute_source_doc(self):
        for r in self:
            r.source_doc = f"sale.order,{r.source_id}" if r.source_id else False

    def init(self):
        """Create or replace the flamant_quotation PostgreSQL view."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    so.id                                                AS id,
                    so.create_date::date                                 AS date,
                    EXTRACT(YEAR  FROM so.create_date)::int              AS year_num,
                    EXTRACT(MONTH FROM so.create_date)::int              AS month_num,
                    so.state                                             AS state,
                    so.team_id                                           AS team_id,
                    so.user_id                                           AS user_id,
                    so.partner_id                                        AS partner_id,
                    t.channel                                          AS channel,
                    t.country_code                                     AS country_code,
                    COALESCE(NULLIF(t.shop_label, ''),
                             t.name->>'en_US')                           AS shop_label,
                    so.validity_date                                     AS validity_date,
                    so.amount_untaxed                                    AS amount_untaxed,
                    so.company_id                                        AS company_id,
                    so.currency_id                                       AS currency_id,
                    so.name                                              AS source_ref,
                    so.id                                                AS source_id
                FROM sale_order so
                LEFT JOIN crm_team t ON t.id = so.team_id
                WHERE so.state IN ('draft', 'sent', 'cancel')
            )
            """
        )
