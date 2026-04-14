from odoo import api, fields, models


class FlamantShopBudget(models.Model):
    _name = 'flamant.shop.budget'
    _description = 'Flamant Monthly Budget per Sales Team'
    _order = 'year desc, month, team_id'
    _sql_constraints = [
        (
            'unique_team_period',
            'unique(team_id, year, month)',
            'Only one budget line per team per month is allowed.',
        ),
    ]

    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        required=True,
        ondelete='cascade',
    )
    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection(
        [
            ('1', 'January'), ('2', 'February'), ('3', 'March'),
            ('4', 'April'), ('5', 'May'), ('6', 'June'),
            ('7', 'July'), ('8', 'August'), ('9', 'September'),
            ('10', 'October'), ('11', 'November'), ('12', 'December'),
        ],
        required=True,
    )
    period_start = fields.Date(
        compute='_compute_period',
        store=True,
        help='First day of the budget month. Usable as a pivot date axis.',
    )
    amount = fields.Monetary(
        string='Budget Amount',
        required=True,
        currency_field='currency_id',
    )
    channel = fields.Selection(related='team_id.x_channel', store=True, readonly=True)
    country_code = fields.Selection(related='team_id.x_country_code', store=True, readonly=True)
    shop_label = fields.Char(
        compute='_compute_shop_label', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    @api.depends('year', 'month')
    def _compute_period(self):
        for rec in self:
            if rec.year and rec.month:
                rec.period_start = fields.Date.to_date(f'{rec.year}-{int(rec.month):02d}-01')
            else:
                rec.period_start = False

    @api.depends('team_id.x_shop_label', 'team_id.name')
    def _compute_shop_label(self):
        for rec in self:
            rec.shop_label = rec.team_id.x_shop_label or rec.team_id.name

    def name_get(self):
        month_labels = dict(self._fields['month'].selection)
        return [
            (
                rec.id,
                f'{rec.team_id.name} — {month_labels.get(rec.month, rec.month)} {rec.year}',
            )
            for rec in self
        ]
