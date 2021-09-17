from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    calculo = fields.Float(string='calcuo')
    @api.multi
    def action_invoice_open(self):
        for acc in self:
            for rec in acc.invoice_line_ids: 
                if not rec.account_analytic_id.id:
                    raise ValidationError(_('Analytic account must be defined '))
        res = super(AccountInvoice, self).action_invoice_open()
        return res 

class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', required="True")