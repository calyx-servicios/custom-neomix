# -*- coding: utf-8 -*-
{
    'name': "l10n_ar_afip_ws_ARCA",
    'summary': """
        This module customizes the lot number labels.
    """,
    'author': "Calyx Servicios S.A",
    "maintainers": ["estebansam21", "enzogonzalezdev"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "11.0.3.0.0",
    "application": False,
    'depends': [
                'l10n_ar_afipws',
                'l10n_ar_afipws_fe'
                ],
    'data': [
        # 'views/res_config_settings.xml',
        'views/report_invoice.xml',
        'views/view_move_form.xml',
        'data/account_tax_group_data.xml'
    ],
}
