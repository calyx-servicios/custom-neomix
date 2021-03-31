##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'
    _name = 'res.company'

    quantity_copy_stock_report = fields.Integer(string="Quantity Copy of Invoice" , default=1)
    logo_stock_report = fields.Binary(string="Company Invoice Logo")