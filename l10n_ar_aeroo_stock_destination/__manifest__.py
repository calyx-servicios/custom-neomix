{
    'name': 'Aeroo Stock report Origin & Destination',
    'summary': """ Adds the fields origin and destination 
        of the internal transfer to aeroo report""",
    'author': 'Calyx Servicios S.A., ADHOC SA',
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
    
    'depends': ['l10n_ar_aeroo_stock','report_aeroo_extra_function'],

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
}
