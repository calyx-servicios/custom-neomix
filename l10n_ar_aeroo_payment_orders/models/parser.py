from odoo import api, models, _

class Parser(models.AbstractModel):
    _inherit = 'report.report_aeroo.abstract'
    _name = 'report.account_payment_group'
    
    
    def _convert_journal_type(self,typee):
        if typee == 'cash':
            return 'Efectivo'
        if typee == 'bank':
            return 'Banco'
        if typee == 'sale':
            return 'Venta'
        if typee == 'purchase':
            return 'Compra'
        if typee == 'General':
            return 'Varios'

    def _get_line_payments(self,o):
        lineas=[]
        print(' aca??????')
        print(' aca??????')

        for line_obj in o.payment_ids:
            print(line_obj)
            print(line_obj.check_ids)
            print(line_obj.tax_withholding_id)

        print(' aca??????')
        print(' aca??????')

        for line_obj in o.payment_ids:
            for check_obj in line_obj.check_ids:
                amount = line_obj.amount 
                tc = ''
                amount_currency = ''
                name_currency = ''
                if line_obj.exchange_rate != 0.0:
                    amount_currency = line_obj.amount
                    tc = _('TC: ')+_(str(line_obj.exchange_rate).replace('.',','))
                    name_currency = line_obj.currency_id.name
                    amount = line_obj.amount * line_obj.exchange_rate
                line = {
                    'nombre': self._convert_journal_type(check_obj.journal_id.type) ,
                    'reference':line_obj.communication,
                    'account': ('Cheque nro %s - %s - Venc. %s')%(check_obj.name, check_obj.bank_id.name or check_obj.journal_id.name, check_obj.payment_date),
                    'name_currency':name_currency,
                    'amount_currency':amount_currency,
                    'tc_currency':tc,
                    'amount':check_obj.amount,
                }
                lineas.append(line)  

        for line_obj in o.payment_ids.filtered(lambda x: x.tax_withholding_id):
            amount = line_obj.amount 
            tc = ''
            amount_currency = ''
            name_currency = ''
            if line_obj.exchange_rate != 0.0:
                amount_currency = line_obj.amount
                tc = _('TC: ')+_(str(line_obj.exchange_rate).replace('.',','))
                name_currency = line_obj.currency_id.name
                amount = line_obj.amount * line_obj.exchange_rate

            line = {
                'nombre':self._convert_journal_type(line_obj.journal_id.type) ,
                'reference':line_obj.communication, 
                'account':("%s - %s")% (line_obj.tax_withholding_id.name, line_obj.withholding_number or line_obj.name),
                'name_currency': name_currency,
                'amount_currency': amount_currency,
                'tc_currency':tc,
                'amount':amount,
            }
            lineas.append(line) 

        for line_obj in o.payment_ids.filtered(lambda x: not x.tax_withholding_id and not x.check_ids):
            amount = line_obj.amount 
            tc = ''
            name_currency = ''
            amount_currency = ''
            if line_obj.exchange_rate != 0.0:
                amount_currency = line_obj.amount
                tc = _('TC: ')+_(str(line_obj.exchange_rate).replace('.',','))
                name_currency = line_obj.currency_id.name
                amount = line_obj.amount * line_obj.exchange_rate

            line = {
                'nombre':self._convert_journal_type(line_obj.journal_id.type),
                'reference':line_obj.communication, 
                'account':line_obj.journal_id.name,
                'name_currency':name_currency,
                'amount_currency':amount_currency,
                'tc_currency':tc,
                'amount':amount,
            }
            lineas.append(line) 

        return lineas


    @api.model
    def aeroo_report(self, docids, data):
        self = self.with_context(get_line_payments=self._get_line_payments)
        return super(Parser, self).aeroo_report(docids, data)



    

        
