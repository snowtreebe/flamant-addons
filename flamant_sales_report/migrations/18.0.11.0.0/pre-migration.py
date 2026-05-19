"""Pre-migration for 18.0.11.0.0 — rename crm.team Flamant fields
(drop x_ prefix) and rename two SQL-view models:

    flamant.daily.sales    → flamant.sales.header
    flamant.product.margin → flamant.sales.line

Runs BEFORE Odoo processes the new model schema, so renamed columns
are already in place when the ORM reads the new field definitions.
This preserves data on prod where x_* values were set manually.
"""
import logging
_logger = logging.getLogger(__name__)

# Column renames on crm_team. Stored OUTSIDE the constants used elsewhere
# so a global find-replace on field names cannot accidentally rewrite the
# source side of the rename.
_CRM_COLUMN_PAIRS = (
    ('x_'     + 'channel',             'channel'),
    ('x_'     + 'country_code',        'country_code'),
    ('x_'     + 'shop_label',          'shop_label'),
    ('x_'     + 'shop_cluster',        'shop_cluster'),
    ('x_'     + 'comparable',          'comparable'),
    ('x_'     + 'analytic_account_id', 'analytic_account_id'),
)

# SQL views to drop (legacy names, recreated under new names by the
# renamed model classes).  Same defensive concatenation trick.
_LEGACY_SQL_VIEWS = (
    'flamant_'  + 'daily_sales',
    'flamant_'  + 'product_margin',
)

# ir_model row renames (model_name string).
_IR_MODEL_PAIRS = (
    ('flamant.' + 'daily.sales',    'flamant.sales.header'),
    ('flamant.' + 'product.margin', 'flamant.sales.line'),
)


def migrate(cr, version):
    if not version:
        return

    # 1. Rename crm.team columns (preserves data set on prod).
    for old, new in _CRM_COLUMN_PAIRS:
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='crm_team' AND column_name=%s",
            (old,),
        )
        if not cr.fetchone():
            continue
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='crm_team' AND column_name=%s",
            (new,),
        )
        if cr.fetchone():
            # Target already created by a prior partial run; copy data
            # over and drop the old column.
            cr.execute(
                f"UPDATE crm_team SET {new} = {old} "
                f"WHERE {new} IS NULL AND {old} IS NOT NULL"
            )
            cr.execute(f"ALTER TABLE crm_team DROP COLUMN {old}")
            _logger.info("Merged crm_team.%s → %s and dropped legacy column", old, new)
        else:
            cr.execute(f"ALTER TABLE crm_team RENAME COLUMN {old} TO {new}")
            _logger.info("Renamed crm_team.%s → %s", old, new)

    # 2. Drop legacy SQL views.  The renamed model classes will recreate
    #    them under flamant_sales_header / flamant_sales_line.
    for view in _LEGACY_SQL_VIEWS:
        cr.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
        _logger.info("Dropped legacy SQL view %s", view)

    # 3. Rename ir_model rows so ir.model.access / ir.model.data references
    #    survive the upgrade.  Only acts when the legacy model still exists.
    for old, new in _IR_MODEL_PAIRS:
        cr.execute("SELECT 1 FROM ir_model WHERE model = %s", (old,))
        if not cr.fetchone():
            continue
        cr.execute("SELECT 1 FROM ir_model WHERE model = %s", (new,))
        if cr.fetchone():
            # Both exist — keep the new one, prune the legacy.
            cr.execute("DELETE FROM ir_model WHERE model = %s", (old,))
            _logger.info("Pruned legacy ir_model row %s (new already present)", old)
        else:
            cr.execute("UPDATE ir_model SET model = %s WHERE model = %s", (new, old))
            _logger.info("Renamed ir_model %s → %s", old, new)
