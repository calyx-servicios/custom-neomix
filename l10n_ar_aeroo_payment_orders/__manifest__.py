{
    'name': 'Argentinian Like Payment Orders Report',
    'version': '11.0.1.2.0',
    'category': 'Report',
    'sequence': 14,
    'author': 'Calyx Servicios S.A.',
    'maintainers': ['AndradeAndrade'],
    'website': 'http://odoo.calyx-cloud.com.ar/',
    'license': 'AGPL-3',
    'summary': 'Modify payment orders',
    'depends': [
        'report_extended_payment_group',
        'l10n_ar_aeroo_base',
        'account_payment_group',
        'account_check',
    ],
    'external_dependencies': {
    },
    'data': [
        'report/payment_report.xml',
        'views/mail_template_data.xml',
        'report/account_transfer_report.xml',
        'views/report_configuration_defaults_data.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
