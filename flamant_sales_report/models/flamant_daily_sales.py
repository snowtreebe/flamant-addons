from odoo import fields, models, tools


class FlamantDailySales(models.Model):
    _name = 'flamant.daily.sales'
    _description = 'Flamant Daily Sales (Order Intake + Invoiced, POS + SO + Customer Invoices)'
    _auto = False
    _order = 'date desc'

    date = fields.Date(readonly=True)
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
    comp_status = fields.Selection(
        [
            ('comparible',     'Comparible'),
            ('non_comparible', 'Non-Comparible'),
        ],
        string='Comparability',
        readonly=True,
    )
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

    def init(self):
        # Consolidated view. For each business event we emit 0, 1 or 2 rows
        # depending on the basis:
        #   - pos.order       -> order_intake AND invoiced (cash sale is both at once)
        #   - sale.order      -> order_intake only (invoice is tracked via account.move)
        #   - account.move    -> invoiced only (out_invoice / out_refund, posted)
        # V18 specifics: pos_order has no currency_id (join res_company),
        # crm_team.name is jsonb (extract with ->>'en_US').
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY d.date, d.team_id, d.basis, d.source) AS id,
                    d.date,
                    d.basis,
                    d.team_id,
                    t.x_channel        AS channel,
                    t.x_country_code   AS country_code,
                    COALESCE(NULLIF(t.x_shop_label, ''), t.name->>'en_US') AS shop_label,
                    COALESCE(NULLIF(t.x_shop_cluster, ''), t.x_shop_label, t.name->>'en_US') AS shop_cluster,
                    t.x_comp_status    AS comp_status,
                    d.source,
                    d.amount_untaxed,
                    d.company_id,
                    rc.currency_id     AS currency_id
                FROM (
                    -- POS orders: order intake
                    SELECT
                        po.date_order::date                AS date,
                        'order_intake'::varchar            AS basis,
                        po.crm_team_id                     AS team_id,
                        'pos'::varchar                     AS source,
                        (po.amount_total - po.amount_tax)  AS amount_untaxed,
                        po.company_id                      AS company_id
                    FROM pos_order po
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL

                    UNION ALL

                    -- POS orders: invoiced (cash sale is both at once)
                    SELECT
                        po.date_order::date,
                        'invoiced'::varchar,
                        po.crm_team_id,
                        'pos'::varchar,
                        (po.amount_total - po.amount_tax),
                        po.company_id
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
                        so.company_id
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                      AND so.team_id IS NOT NULL

                    UNION ALL

                    -- Customer invoices (out_invoice) / credit notes (out_refund): invoiced only
                    SELECT
                        am.invoice_date::date,
                        'invoiced'::varchar,
                        am.team_id,
                        'invoice'::varchar,
                        CASE
                            WHEN am.move_type = 'out_refund' THEN -am.amount_untaxed
                            ELSE am.amount_untaxed
                        END,
                        am.company_id
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
