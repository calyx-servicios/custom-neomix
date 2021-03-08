# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Aeroo Stock report Origin & Destination',
    'summary': """ Adds the fields origin and destination 
        of the internal transfer to aeroo report""",

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
    
    'depends': ['l10n_ar_aeroo_stock'],

    'data': [
        'views/report_configuration_defaults_data.xml',
        'views/report.xml',
        ]
}
