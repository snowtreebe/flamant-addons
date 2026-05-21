from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    flamant_margin_locked = fields.Monetary(
        string='Locked Margin',
        currency_field='currency_id',
        readonly=True,
        copy=False,
        help='Cached margin (revenue - cost) computed by the Flamant locked-margin '
             'cron. Refreshed daily for the current month; finalized on the 1st of '
             'the next month and never written again. Used to detect post-order '
             'purchase-price drift in the Order Intake Lines report.',
    )
