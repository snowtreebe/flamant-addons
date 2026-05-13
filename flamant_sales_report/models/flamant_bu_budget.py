from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


BU_SELECTION = [
    ('retail_be',  'Retail / Belgium'),
    ('retail_fr',  'Retail / France'),
    ('ecom_be',    'Ecommerce / Belgium'),
    ('ecom_fr',    'Ecommerce / France'),
    ('ecom_int',   'Ecommerce / International'),
    ('wholesale',  'Wholesale'),
    ('other',      'Other (Outlet)'),
]

MONTH_SELECTION = [
    ('1',  'January'),  ('2',  'February'), ('3',  'March'),
    ('4',  'April'),    ('5',  'May'),      ('6',  'June'),
    ('7',  'July'),     ('8',  'August'),   ('9',  'September'),
    ('10', 'October'),  ('11', 'November'), ('12', 'December'),
]


class FlamantBuBudget(models.Model):
    """One omzet-budget row per Business Unit per month.

    Two amounts side-by-side:
      - locked_amount    : budget set by the board (RvB), free-edit for now
      - estimated_amount : rolling forecast, always overwritten with latest

    Parent rows in the BU report (Retail, Ecommerce, TOTAAL) are computed by
    aggregation of the leaf rows; do not enter parent-level budgets here.
    """

    _name = 'flamant.bu.budget'
    _description = 'Flamant Business Unit Budget (Omzet)'
    _order = 'year desc, month, business_unit'
    _sql_constraints = [
        (
            'unique_bu_period',
            'unique(business_unit, year, month, company_id)',
            'Only one budget row per Business Unit per month per company.',
        ),
    ]

    business_unit = fields.Selection(BU_SELECTION, required=True, string='Business Unit')
    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection(MONTH_SELECTION, required=True,
                             default=lambda self: str(fields.Date.today().month))
    period_start = fields.Date(
        compute='_compute_period_start', store=True,
        help='First day of the budget month - usable as a pivot date axis.',
    )
    locked_amount = fields.Monetary(string='Locked Budget (Omzet)', currency_field='currency_id')
    estimated_amount = fields.Monetary(string='Estimated Budget (Omzet)', currency_field='currency_id')
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends('year', 'month')
    def _compute_period_start(self):
        for rec in self:
            if rec.year and rec.month:
                rec.period_start = fields.Date.to_date(f'{rec.year}-{int(rec.month):02d}-01')
            else:
                rec.period_start = False

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year and (rec.year < 2000 or rec.year > 2100):
                raise ValidationError(_('Year must be between 2000 and 2100.'))

    def name_get(self):
        bu_labels = dict(BU_SELECTION)
        month_labels = dict(MONTH_SELECTION)
        return [
            (
                rec.id,
                f'{bu_labels.get(rec.business_unit, rec.business_unit)} - '
                f'{month_labels.get(rec.month, rec.month)} {rec.year}',
            )
            for rec in self
        ]
