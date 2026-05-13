from odoo import models


class FlamantBgReportHandler(models.AbstractModel):
    """Handler for the GROUPED variant of the BU report.

    Inherits the leaf-budget engine from the flat handler and adds an
    extra "Actuals | Budgets" supercolumn header via the native
    `custom_columns_subheaders` mechanism on `account.report`.
    """

    _name = 'flamant.bg.report.handler'
    _inherit = 'flamant.bu.report.handler'
    _description = 'Flamant BU Report Custom Handler (Grouped Header)'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['custom_columns_subheaders'] = [
            {'name': 'Actuals', 'colspan': 4},
            {'name': 'Budgets', 'colspan': 6},
        ]
