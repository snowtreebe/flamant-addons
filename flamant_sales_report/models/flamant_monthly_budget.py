from odoo import fields, models, tools


class FlamantMonthlyBudget(models.Model):
    """Read-only view: monthly budget per sales team from Odoo's account.budget.

    Joins budget_line → account.analytic.account → crm.team via
    analytic_account_id, so the same channel/country/shop dimensions as
    flamant.sales.header are available for pivot reporting.

    Only lines whose analytic account is linked to at least one sales team
    are included.
    """

    _name = 'flamant.monthly.budget'
    _description = 'Flamant Monthly Budget (from account.budget)'
    _auto = False
    _order = 'period_start, team_id'

    period_start = fields.Date(readonly=True)
    year_num = fields.Integer(readonly=True)
    month_num = fields.Integer(readonly=True)
    team_id = fields.Many2one('crm.team', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', readonly=True)
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
        [('BE', 'Belgium'), ('FR', 'France'), ('INT', 'International'), ('OTHER', 'Other')],
        string='Country',
        readonly=True,
    )
    shop_label = fields.Char(readonly=True)
    shop_cluster = fields.Char(readonly=True)
    amount = fields.Monetary(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        """Create or replace the flamant_monthly_budget PostgreSQL view."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY bl.date_from, t.id) AS id,
                    bl.date_from                                                   AS period_start,
                    EXTRACT(YEAR  FROM bl.date_from)::int                          AS year_num,
                    EXTRACT(MONTH FROM bl.date_from)::int                          AS month_num,
                    t.id                                                           AS team_id,
                    bl.account_id                                                  AS analytic_account_id,
                    t.channel                                                    AS channel,
                    t.country_code                                               AS country_code,
                    COALESCE(NULLIF(t.shop_label, ''), t.name->>'en_US')         AS shop_label,
                    COALESCE(NULLIF(t.shop_cluster, ''), t.shop_label,
                             t.name->>'en_US')                                     AS shop_cluster,
                    bl.budget_amount                                               AS amount,
                    bl.company_id                                                  AS company_id,
                    rc.currency_id                                                 AS currency_id
                FROM budget_line bl
                JOIN crm_team     t  ON t.analytic_account_id = bl.account_id
                JOIN res_company  rc ON rc.id = bl.company_id
                WHERE bl.account_id IS NOT NULL
            )
            """
        )
