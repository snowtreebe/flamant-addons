from odoo import fields, models, tools


class FlamantDailySales(models.Model):
    _name = 'flamant.daily.sales'
    _description = 'Flamant Daily Sales (POS + SO consolidated)'
    _auto = False
    _order = 'date desc'

    date = fields.Date(readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    channel = fields.Selection(
        [
            ('wholesale', 'Wholesale'),
            ('shops', 'Shops'),
            ('ecommerce', 'E-Commerce'),
            ('other', 'Other'),
        ],
        readonly=True,
    )
    country_code = fields.Selection(
        [
            ('BE', 'Belgium'),
            ('FR', 'France'),
            ('OTHER', 'Other'),
        ],
        string='Country',
        readonly=True,
    )
    shop_label = fields.Char(readonly=True)
    source = fields.Selection(
        [('pos', 'POS'), ('sale', 'Sale Order')],
        readonly=True,
    )
    amount_untaxed = fields.Monetary(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY d.date, d.team_id, d.source) AS id,
                    d.date,
                    d.team_id,
                    t.x_channel        AS channel,
                    t.x_country_code   AS country_code,
                    COALESCE(NULLIF(t.x_shop_label, ''), t.name) AS shop_label,
                    d.source,
                    d.amount_untaxed,
                    d.company_id,
                    d.currency_id
                FROM (
                    SELECT
                        po.date_order::date                AS date,
                        po.crm_team_id                     AS team_id,
                        'pos'::varchar                     AS source,
                        (po.amount_total - po.amount_tax)  AS amount_untaxed,
                        po.company_id                      AS company_id,
                        po.currency_id                     AS currency_id
                    FROM pos_order po
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL
                    UNION ALL
                    SELECT
                        so.date_order::date                AS date,
                        so.team_id                         AS team_id,
                        'sale'::varchar                    AS source,
                        so.amount_untaxed                  AS amount_untaxed,
                        so.company_id                      AS company_id,
                        so.currency_id                     AS currency_id
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                      AND so.team_id IS NOT NULL
                ) d
                LEFT JOIN crm_team t ON t.id = d.team_id
            )
            """
        )
