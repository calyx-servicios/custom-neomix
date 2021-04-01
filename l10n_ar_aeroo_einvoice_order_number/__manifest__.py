{
    'name': 'Aeroo einvoice purchase order number',
    'summary': """ Adds the field purchase order number 
     to the aeroo report""",
    'author': 'Calyx Servicios S.A., ADHOC SA',
    'maintainers': ['Paradiso Cristian'],
    'version': '11.0.1.0.0',
    'website': 'http://odoo.calyx-cloud.com.ar/',
    'license': 'AGPL-3',
    'depends': [
        'l10n_ar_aeroo_einvoice',
    ],
    'external_dependencies': {
    },
    'data': [
        'report/invoice_report.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}

