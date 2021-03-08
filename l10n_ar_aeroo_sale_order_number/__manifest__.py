# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Aeroo Sale OC number',
    'summary': """ Adds the field sale order number to aeroo report
     when the sale oreder is confirm""",

    'author': 'Calyx Servicios S.A., Odoo Community Association (OCA)',
    'maintainers': ['Paradiso Cristian'],

    'website': 'http://odoo.calyx-cloud.com.ar/',
    'license': 'AGPL-3',

    'category': 'Technical Settings',
    'version': '11.0.1.0.0',
    # see https://odoo-community.org/page/development-status
    'development_status': 'Production/Stable',

    'application': False,
    'installable': True,

    # any module necessary for this one to work correctly
    'depends': ['l10n_ar_aeroo_sale'],

    'data': [
        'views/report_configuration_defaults_data.xml',
        'views/sale_order_report.xml',
        'views/sale_order_template.xml',
    ],
}
