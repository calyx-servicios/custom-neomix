# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    'name': 'Aeroo Stock report Origin & Destination',
    'summary': """ Adds the fields origin and destination 
        of the internal transfer to aeroo report""",

    'author': 'Calyx Servicios S.A., Odoo Community Association (OCA)',
    'maintainers': ['Paradiso Cristian'],

    'website': 'http://odoo.calyx-cloud.com.ar/',
    'license': 'AGPL-3',
    'depends': [
        'l10n_ar_aeroo_stock',
    ],
    'external_dependencies': {
    },
    'data': [
        'report/report.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'installable': True,
    
    'depends': ['l10n_ar_aeroo_stock'],

    'data': [
        'views/report_configuration_defaults_data.xml',
        'views/report.xml',
        ]
}
