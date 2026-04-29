from odoo import api, fields, models, tools


class FlamantDailySales(models.Model):
    """Read-only consolidated view of POS orders, sale orders, and customer
    invoices. Each source record can emit up to two rows: one for order_intake
    and one for invoiced basis (POS orders emit both; sale orders only
    order_intake; invoices only invoiced).

    V18 notes:
    - pos_order has no currency_id column — derived from res_company.
    - crm_team.name is jsonb — extracted with ->>'en_US'.
    """

    _name = 'flamant.daily.sales'
    _description = 'Flamant Daily Sales (POS + Sale Orders + Invoices)'
    _auto = False
    _order = 'date desc'

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
    basis = fields.Selection(
        [
            ('order_intake', 'Order Intake'),
            ('invoiced',     'Invoiced Sales'),
        ],
        readonly=True,
    )
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
    source = fields.Selection(
        [
            ('pos',     'POS'),
            ('sale',    'Sale Order'),
            ('invoice', 'Customer Invoice'),
        ],
        readonly=True,
    )
    amount_untaxed = fields.Monetary(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    # Source-document traceability — links each row back to its origin record.
    source_model = fields.Char(string='Source Model', readonly=True)
    source_id    = fields.Integer(string='Source ID', readonly=True)
    source_ref   = fields.Char(string='Reference', readonly=True)

    source_doc = fields.Reference(
        selection=[
            ('pos.order',    'POS Order'),
            ('sale.order',   'Sales Order'),
            ('account.move', 'Invoice'),
        ],
        string='Document',
        compute='_compute_source_doc',
    )

    @api.depends('source_model', 'source_id')
    def _compute_source_doc(self):
        """Return a Reference value pointing to the originating record."""
        for r in self:
            if r.source_model and r.source_id:
                r.source_doc = f"{r.source_model},{r.source_id}"
            else:
                r.source_doc = False

    def init(self):
        """Create or replace the flamant_daily_sales PostgreSQL view.

        Each source record emits rows depending on its type:
          - pos.order    → order_intake AND invoiced (cash sale covers both)
          - sale.order   → order_intake only
          - account.move → invoiced only (out_invoice / out_refund, posted)
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY d.date, d.team_id, d.basis, d.source, d.source_id
                    ) AS id,
                    d.date,
                    EXTRACT(YEAR  FROM d.date)::int AS year_num,
                    EXTRACT(MONTH FROM d.date)::int AS month_num,
                    -- PostgreSQL dow: 0=Sun..6=Sat → remap to ISO Mon=1..Sun=7
                    CASE EXTRACT(DOW FROM d.date)::int
                        WHEN 0 THEN '7' ELSE EXTRACT(DOW FROM d.date)::text
                    END AS weekday_num,
                    d.basis,
                    d.team_id,
                    t.x_channel                                                    AS channel,
                    t.x_country_code                                               AS country_code,
                    COALESCE(NULLIF(t.x_shop_label, ''), t.name->>'en_US')         AS shop_label,
                    COALESCE(NULLIF(t.x_shop_cluster, ''), t.x_shop_label,
                             t.name->>'en_US')                                     AS shop_cluster,
                    d.source,
                    d.amount_untaxed,
                    d.company_id,
                    rc.currency_id                                                  AS currency_id,
                    d.source_model,
                    d.source_id,
                    d.source_ref
                FROM (
                    -- POS orders: order intake
                    SELECT
                        po.date_order::date                              AS date,
                        'order_intake'::varchar                          AS basis,
                        po.crm_team_id                                   AS team_id,
                        'pos'::varchar                                   AS source,
                        (po.amount_total - po.amount_tax)                AS amount_untaxed,
                        po.company_id                                    AS company_id,
                        'pos.order'::varchar                             AS source_model,
                        po.id                                            AS source_id,
                        COALESCE(NULLIF(po.pos_reference, ''), po.name) AS source_ref
                    FROM pos_order po
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL

                    UNION ALL

                    -- POS orders: invoiced (cash sale counts as both)
                    SELECT
                        po.date_order::date,
                        'invoiced'::varchar,
                        po.crm_team_id,
                        'pos'::varchar,
                        (po.amount_total - po.amount_tax),
                        po.company_id,
                        'pos.order'::varchar,
                        po.id,
                        COALESCE(NULLIF(po.pos_reference, ''), po.name)
                    FROM pos_order po
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL

                    UNION ALL

                    -- Sale orders: order intake only
                    SELECT
                        so.date_order::date,
                        'order_intake'::varchar,
                        so.team_id,
                        'sale'::varchar,
                        so.amount_untaxed,
                        so.company_id,
                        'sale.order'::varchar,
                        so.id,
                        so.name
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                      AND so.team_id IS NOT NULL

                    UNION ALL

                    -- Customer invoices and credit notes: invoiced only
                    SELECT
                        am.invoice_date::date,
                        'invoiced'::varchar,
                        am.team_id,
                        'invoice'::varchar,
                        CASE
                            WHEN am.move_type = 'out_refund' THEN -am.amount_untaxed
                            ELSE am.amount_untaxed
                        END,
                        am.company_id,
                        'account.move'::varchar,
                        am.id,
                        am.name
                    FROM account_move am
                    WHERE am.state = 'posted'
                      AND am.move_type IN ('out_invoice', 'out_refund')
                      AND am.team_id IS NOT NULL
                      AND am.invoice_date IS NOT NULL
                ) d
                LEFT JOIN crm_team    t  ON t.id  = d.team_id
                LEFT JOIN res_company rc ON rc.id = d.company_id
            )
            """
        )
