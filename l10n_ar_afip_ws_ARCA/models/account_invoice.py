# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
import base64
from io import BytesIO
import logging
import json
import sys
import traceback
from datetime import datetime
from odoo.tools.misc import formatLang
_logger = logging.getLogger(__name__)

try:
    import qrcode
except ImportError:
    qrcode = None
try:
    from pysimplesoap.client import SoapFault
except ImportError:
    _logger.debug('Can not `from pyafipws.soap import SoapFault`.')


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    def get_tax_detail_ar(self):
        involved_tax_group_ids = []
        for line in self.tax_line_ids:
            involved_tax_group_ids.append(line.tax_id.tax_group_id.id)
        involved_tax_groups = self.env['account.tax.group'].browse(involved_tax_group_ids)
        nat_tax_groups = involved_tax_groups.filtered(lambda tax_group: tax_group.afip_code in (1, 4))
        vat_tax_groups = involved_tax_groups.filtered(lambda tax_group: tax_group.afip_code != 0)

        # RG 5614/2024: Show ARCA VAT and Other National Internal Taxes
        if self.journal_document_type_id.document_type_id.code in ['6', '7', '8']:
            # Prepare the subtotals to show in the report
            currency_symbol = self.currency_id.symbol
            detail_info = {}

            for line in self.tax_line_ids:
                if line.tax_id.tax_group_id in nat_tax_groups:
                    key = 'other_taxes'
                    name = _("Other National Ind. Taxes %s") % currency_symbol
                elif line.tax_id.tax_group_id in vat_tax_groups:
                    key = 'vat_taxes'
                    name = _("VAT Content %s") % currency_symbol
                else:
                    continue

                if key not in detail_info:
                    if line.amount_total != 0.0:
                        detail_info[key] = {"name": name, "tax_amount": line.amount_total}
                else:
                    detail_info[key]["tax_amount"] += line.amount_total

            # Format the amounts to show in the report
            for _item, values in detail_info.items():
                values["formatted_amount_tax"] = formatLang(self.env, values["tax_amount"])

            return list(detail_info.values())

    l10n_ar_payment_foreign_currency = fields.Selection(
        [("S", "Yes"), ("N", "No")],
        # compute="compute_l10n_ar_payment_foreign_currency",
        store=True,
        readonly=False
    )
    l10n_ar_currency_code = fields.Char("Currency Code", related="currency_id.name")

    # @api.onchange("currency_id", "line_ids")
    # @api.depends("currency_id")
    # def compute_l10n_ar_payment_foreign_currency(self):
    #     self.l10n_ar_payment_foreign_currency = False
    #     for move in self:
    #         default_value = move.company_id.l10n_ar_payment_foreign_currency
    #         if default_value == "account":
    #             account = move.line_ids.account_id.filtered(lambda x: x.account_type == "asset_receivable")
    #             default_value = "S" if account.currency_id and account.currency_id != move.company_currency_id else "N"
    #         move.l10n_ar_payment_foreign_currency = default_value

    def get_pyafipws_currency_rate(self):
        self.ensure_one()
        afip_ws = self.journal_id.afip_ws
        ws = self.company_id.get_connection(afip_ws).connect()
        afipws_get_currency_rate = self.pyafipws_get_currency_rate(ws)
        # TODO: crear cotizacion?
        self._set_afip_rate()
        notification = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _(
                    "Actual afip rate is %s" % afipws_get_currency_rate
                ),
                "type": "success",
                "sticky": True,  # True/False will display for few seconds if false
            },
        }
        return notification


    @api.multi
    def do_pyafipws_request_cae(self):
        "Request to AFIP the invoices' Authorization Electronic Code (CAE)"
        for inv in self:
            # Ignore invoices with cae (do not check date)
            if inv.afip_auth_code:
                continue

            if inv.journal_id.point_of_sale_type != 'electronic':
                continue
            afip_ws = inv.journal_id.afip_ws
            # Ignore invoice if not ws on point of sale
            if not afip_ws:
                raise UserError(_(
                    'If you use electronic journals (invoice id %s) you need '
                    'configure AFIP WS on the journal') % (inv.id))

            # if no validation type and we are on electronic invoice, it means
            # that we are on a testing database without homologation
            # certificates
            if not inv.validation_type:
                msg = (
                    'Factura validada solo localmente por estar en ambiente '
                    'de homologacion sin claves de homologacion')
                inv.write({
                    'afip_auth_mode': 'CAE',
                    'afip_auth_code': '68448767638166',
                    'afip_auth_code_due': inv.date_invoice,
                    'afip_result': '',
                    'afip_message': msg,
                })
                inv.message_post(msg)
                continue

            # get the electronic invoice type, point of sale and afip_ws:
            commercial_partner = inv.commercial_partner_id
            country = commercial_partner.country_id
            journal = inv.journal_id
            pos_number = journal.point_of_sale_number
            doc_afip_code = inv.document_type_id.code

            # authenticate against AFIP:
            ws = inv.company_id.get_connection(afip_ws).connect()

            if afip_ws == 'wsfex':
                if not country:
                    raise UserError(_(
                        'For WS "%s" country is required on partner' % (
                            afip_ws)))
                elif not country.code:
                    raise UserError(_(
                        'For WS "%s" country code is mandatory'
                        'Country: %s' % (
                            afip_ws, country.name)))
                elif not country.afip_code:
                    raise UserError(_(
                        'For WS "%s" country afip code is mandatory'
                        'Country: %s' % (
                            afip_ws, country.name)))

            ws_next_invoice_number = int(
                inv.journal_document_type_id.get_pyafipws_last_invoice(
                )['result']) + 1
            # verify that the invoice is the next one to be registered in AFIP
            if inv.invoice_number != ws_next_invoice_number:
                raise UserError(_(
                    'Error!'
                    'Invoice id: %i'
                    'Next invoice number should be %i and not %i' % (
                        inv.id,
                        ws_next_invoice_number,
                        inv.invoice_number)))

            partner_id_code = commercial_partner.main_id_category_id.afip_code
            tipo_doc = partner_id_code or '99'
            nro_doc = \
                partner_id_code and commercial_partner.main_id_number or "0"
            cbt_desde = cbt_hasta = cbte_nro = inv.invoice_number
            concepto = tipo_expo = int(inv.afip_concept)

            fecha_cbte = inv.date_invoice
            if afip_ws != 'wsmtxca':
                fecha_cbte = fecha_cbte.replace("-", "")

            mipyme_fce = int(doc_afip_code) in [201, 206, 211]
            # due date only for concept "services" and mipyme_fce
            if int(concepto) != 1 and int(doc_afip_code) not in [202, 203, 207, 208, 212, 213] or mipyme_fce:
                fecha_venc_pago = inv.date_due or inv.date_invoice
                if afip_ws != 'wsmtxca':
                    fecha_venc_pago = fecha_venc_pago.replace("-", "")
            else:
                fecha_venc_pago = None

            # fecha de servicio solo si no es 1
            if int(concepto) != 1:
                fecha_serv_desde = inv.afip_service_start
                fecha_serv_hasta = inv.afip_service_end
                if afip_ws != 'wsmtxca':
                    fecha_serv_desde = fecha_serv_desde.replace("-", "")
                    fecha_serv_hasta = fecha_serv_hasta.replace("-", "")
            else:
                fecha_serv_desde = fecha_serv_hasta = None

            # # invoice amount totals:
            imp_total = str("%.2f" % inv.amount_total)
            # ImpTotConc es el iva no gravado
            imp_tot_conc = str("%.2f" % inv.vat_untaxed_base_amount)
            # tal vez haya una mejor forma, la idea es que para facturas c
            # no se pasa iva. Probamos hacer que vat_taxable_amount
            # incorpore a los imp cod 0, pero en ese caso termina reportando
            # iva y no lo queremos
            if inv.document_type_id.document_letter_id.name == 'C':
                imp_neto = str("%.2f" % inv.amount_untaxed)
            else:
                imp_neto = str("%.2f" % inv.vat_taxable_amount)
            imp_iva = str("%.2f" % inv.vat_amount)
            # se usaba para wsca..
            # imp_subtotal = str("%.2f" % inv.amount_untaxed)
            imp_trib = str("%.2f" % inv.other_taxes_amount)
            imp_op_ex = str("%.2f" % inv.vat_exempt_base_amount)
            moneda_id = inv.currency_id.afip_code
            moneda_ctz = inv.currency_rate
            cancela_misma_moneda_ext= inv.l10n_ar_payment_foreign_currency
            condicion_iva_receptor_id= inv.commercial_partner_id.afip_responsability_type_id.code

            CbteAsoc = inv.get_related_invoices_data()

            # create the invoice internally in the helper
            if afip_ws == 'wsfe':
                ws.CrearFactura(
                    concepto, tipo_doc, nro_doc, doc_afip_code, pos_number,
                    cbt_desde, cbt_hasta, imp_total, imp_tot_conc, imp_neto,
                    imp_iva,
                    imp_trib, imp_op_ex, fecha_cbte, fecha_venc_pago,
                    fecha_serv_desde, fecha_serv_hasta,
                    moneda_id, moneda_ctz, cancela_misma_moneda_ext, condicion_iva_receptor=condicion_iva_receptor_id
                )
            # elif afip_ws == 'wsmtxca':
            #     obs_generales = inv.comment
            #     ws.CrearFactura(
            #         concepto, tipo_doc, nro_doc, doc_afip_code, pos_number,
            #         cbt_desde, cbt_hasta, imp_total, imp_tot_conc, imp_neto,
            #         imp_subtotal,   # difference with wsfe
            #         imp_trib, imp_op_ex, fecha_cbte, fecha_venc_pago,
            #         fecha_serv_desde, fecha_serv_hasta,
            #         moneda_id, moneda_ctz,
            #         obs_generales   # difference with wsfe
            #     )
            elif afip_ws == 'wsfex':
                # # foreign trade data: export permit, country code, etc.:
                if inv.afip_incoterm_id:
                    incoterms = inv.afip_incoterm_id.afip_code
                    incoterms_ds = inv.afip_incoterm_id.name
                    # maximo de 20 caracteres admite
                    incoterms_ds = incoterms_ds and incoterms_ds[:20]
                else:
                    incoterms = incoterms_ds = None
                # por lo que verificamos, se pide permiso existente solo
                # si es tipo expo 1 y es factura (codigo 19), para todo el
                # resto pasamos cadena vacia
                if int(doc_afip_code) == 19 and tipo_expo == 1:
                    # TODO investigar si hay que pasar si ("S")
                    permiso_existente = "N"
                else:
                    permiso_existente = ""
                obs_generales = inv.comment

                if inv.payment_term_id:
                    forma_pago = inv.payment_term_id.name
                    obs_comerciales = inv.payment_term_id.name
                else:
                    forma_pago = obs_comerciales = None

                # 1671 Report fecha_pago with format YYYMMDD
                # 1672 Is required only doc_type 19. concept (2,4)
                # 1673 If doc_type != 19 should not be reported.
                # 1674 doc_type 19 concept (2,4). date should be >= invoice date
                fecha_pago = datetime.strftime(fields.Datetime.from_string(inv.date_due), '%Y%m%d') \
                    if int(doc_afip_code) == 19 and tipo_expo in [2, 4] and inv.date_due else ''

                idioma_cbte = 1     # invoice language: spanish / espa nol

                # TODO tal vez podemos unificar este criterio con el del
                # citi que pide el cuit al partner
                # customer data (foreign trade):
                nombre_cliente = commercial_partner.name
                # se debe informar cuit pais o id_impositivo
                if nro_doc:
                    id_impositivo = nro_doc
                    cuit_pais_cliente = None
                elif country.code != 'AR' and nro_doc:
                    id_impositivo = None
                    if commercial_partner.is_company:
                        cuit_pais_cliente = country.cuit_juridica
                    else:
                        cuit_pais_cliente = country.cuit_fisica
                    if not cuit_pais_cliente:
                        raise UserError(_(
                            'No vat defined for the partner and also no CUIT '
                            'set on country'))

                domicilio_cliente = " - ".join([
                    commercial_partner.name or '',
                    commercial_partner.street or '',
                    commercial_partner.street2 or '',
                    commercial_partner.zip or '',
                    commercial_partner.city or '',
                ])
                pais_dst_cmp = commercial_partner.country_id.afip_code
                ws.CrearFactura(
                    doc_afip_code, pos_number, cbte_nro, fecha_cbte,
                    imp_total, tipo_expo, permiso_existente, pais_dst_cmp,
                    nombre_cliente, cuit_pais_cliente, domicilio_cliente,
                    id_impositivo, moneda_id, moneda_ctz, obs_comerciales,
                    obs_generales, forma_pago, incoterms,
                    idioma_cbte, incoterms_ds, fecha_pago,
                )
            elif afip_ws == 'wsbfe':
                zona = 1  # Nacional (la unica devuelta por afip)
                # los responsables no inscriptos no se usan mas
                impto_liq_rni = 0.0
                imp_iibb = sum(inv.tax_line_ids.filtered(lambda r: (
                    r.tax_id.tax_group_id.type == 'perception' and
                    r.tax_id.tax_group_id.application == 'provincial_taxes')
                ).mapped('amount'))
                imp_perc_mun = sum(inv.tax_line_ids.filtered(lambda r: (
                    r.tax_id.tax_group_id.type == 'perception' and
                    r.tax_id.tax_group_id.application == 'municipal_taxes')
                ).mapped('amount'))
                imp_internos = sum(inv.tax_line_ids.filtered(
                    lambda r: r.tax_id.tax_group_id.application == 'others'
                ).mapped('amount'))
                imp_perc = sum(inv.tax_line_ids.filtered(lambda r: (
                    r.tax_id.tax_group_id.type == 'perception' and
                    # r.tax_id.tax_group_id.tax != 'vat' and
                    r.tax_id.tax_group_id.application == 'national_taxes')
                ).mapped('amount'))

                ws.CrearFactura(
                    tipo_doc, nro_doc, zona, doc_afip_code, pos_number,
                    cbte_nro, fecha_cbte, imp_total, imp_neto, imp_iva,
                    imp_tot_conc, impto_liq_rni, imp_op_ex, imp_perc, imp_iibb,
                    imp_perc_mun, imp_internos, moneda_id, moneda_ctz, fecha_venc_pago,
                    cancela_misma_moneda_ext, condicion_iva_receptor=condicion_iva_receptor_id,
                )

            if afip_ws in ['wsfe', 'wsbfe']:
                if mipyme_fce:
                    # agregamos cbu para factura de credito electronica
                    ws.AgregarOpcional(
                        opcional_id=2101,
                        valor=inv.partner_bank_id.cbu)

                    # agregamos tipo de transmision si esta definido
                    transmission_type = self.env['ir.config_parameter'].sudo().get_param(
                        'l10n_ar_edi.fce_transmission', '')
                    if transmission_type:
                        ws.AgregarOpcional(
                            opcional_id=27,
                            valor=transmission_type)
                    if inv.name:
                        ws.AgregarOpcional(
                            opcional_id=23,
                            valor=inv.name)
                elif int(doc_afip_code) in [202, 203, 207, 208, 212, 213]:
                    valor = inv.afip_fce_es_anulacion and 'S' or 'N'
                    ws.AgregarOpcional(
                        opcional_id=22,
                        valor=valor)

            # TODO ver si en realidad tenemos que usar un vat pero no lo
            # subimos
            if afip_ws not in ['wsfex', 'wsbfe']:
                for vat in inv.vat_taxable_ids:
                    _logger.info(
                        'Adding VAT %s' % vat.tax_id.tax_group_id.name)
                    ws.AgregarIva(
                        vat.tax_id.tax_group_id.afip_code,
                        "%.2f" % vat.base,
                        # "%.2f" % abs(vat.base_amount),
                        "%.2f" % vat.amount,
                    )

                for tax in inv.not_vat_tax_ids:
                    _logger.info(
                        'Adding TAX %s' % tax.tax_id.tax_group_id.name)
                    ws.AgregarTributo(
                        tax.tax_id.tax_group_id.application_code,
                        tax.tax_id.tax_group_id.name,
                        "%.2f" % tax.base,
                        # "%.2f" % abs(tax.base_amount),
                        # TODO pasar la alicuota
                        # como no tenemos la alicuota pasamos cero, en v9
                        # podremos pasar la alicuota
                        0,
                        "%.2f" % tax.amount,
                    )

            if CbteAsoc:
                # fex no acepta fecha
                if afip_ws == 'wsfex':
                    ws.AgregarCmpAsoc(
                        CbteAsoc.document_type_id.code,
                        CbteAsoc.point_of_sale_number,
                        CbteAsoc.invoice_number,
                        self.company_id.cuit,
                    )
                else:
                    ws.AgregarCmpAsoc(
                        CbteAsoc.document_type_id.code,
                        CbteAsoc.point_of_sale_number,
                        CbteAsoc.invoice_number,
                        self.company_id.cuit,
                        afip_ws != 'wsmtxca' and CbteAsoc.date_invoice.replace("-", "") or CbteAsoc.date_invoice,
                    )
            else:
                if afip_ws == 'wsfe' and self.document_type_id.internal_type in ['credit_note', 'debit_note'] and  \
                   self.afip_asoc_period_start and self.afip_asoc_period_end:
                    ws.AgregarPeriodoComprobantesAsociados(
                        fecha_desde=self.afip_asoc_period_start.replace("-", ""),
                        fecha_hasta=self.afip_asoc_period_end.replace("-", ""),
                    )

            # analize line items - invoice detail
            # wsfe do not require detail
            if afip_ws != 'wsfe':
                for line in inv.invoice_line_ids:
                    codigo = line.product_id.product_tmpl_id.l10n_ar_ncm_code or line.product_id.default_code
                    # unidad de referencia del producto si se comercializa
                    # en una unidad distinta a la de consumo
                    # uom is not mandatory, if no UOM we use "unit"
                    if not line.uom_id:
                        umed = '7'
                    elif not line.uom_id.afip_code:
                        raise UserError(_(
                            'Not afip code con producto UOM %s' % (
                                line.uom_id.name)))
                    else:
                        umed = line.uom_id.afip_code
                    # cod_mtx = line.uom_id.afip_code
                    ds = line.name
                    qty = line.quantity
                    precio = line.price_unit
                    importe = line.price_subtotal
                    # calculamos bonificacion haciendo teorico menos importe
                    bonif = line.discount and str(
                        "%.2f" % (precio * qty - importe)) or None
                    if afip_ws in ['wsmtxca', 'wsbfe']:
                        # TODO No lo estamos usando. Borrar?
                        # if not line.product_id.uom_id.afip_code:
                        #     raise UserError(_(
                        #         'Not afip code con producto UOM %s' % (
                        #             line.product_id.uom_id.name)))
                        # u_mtx = (
                        #     line.product_id.uom_id.afip_code or
                        #     line.uom_id.afip_code)
                        iva_id = line.vat_tax_id.tax_group_id.afip_code
                        vat_taxes_amounts = line.vat_tax_id.compute_all(
                            line.price_unit, inv.currency_id, line.quantity,
                            product=line.product_id,
                            partner=inv.partner_id)
                        imp_iva = sum(
                            [x['amount'] for x in vat_taxes_amounts['taxes']])
                        if afip_ws == 'wsmtxca':
                            raise UserError(
                                _('WS wsmtxca Not implemented yet'))
                            # ws.AgregarItem(
                            #     u_mtx, cod_mtx, codigo, ds, qty, umed,
                            #     precio, bonif, iva_id, imp_iva,
                            #     importe + imp_iva)
                        elif afip_ws == 'wsbfe':
                            sec = ""  # Codigo de la Secretaria (TODO usar)
                            ws.AgregarItem(
                                codigo, sec, ds, qty, umed, precio, bonif,
                                iva_id, importe + imp_iva)
                    elif afip_ws == 'wsfex':
                        ws.AgregarItem(
                            codigo, ds, qty, umed, precio, "%.2f" % importe,
                            bonif)

            # Request the authorization! (call the AFIP webservice method)
            vto = None
            msg = False
            try:
                if afip_ws == 'wsfe':
                    ws.CAESolicitar()
                    vto = ws.Vencimiento
                elif afip_ws == 'wsmtxca':
                    ws.AutorizarComprobante()
                    vto = ws.Vencimiento
                elif afip_ws == 'wsfex':
                    last_id = ws.GetLastID()
                    ws.Authorize(last_id+1)
                    vto = ws.FchVencCAE
                elif afip_ws == 'wsbfe':
                    last_id = ws.GetLastID()
                    ws.Authorize(last_id+1)
                    vto = ws.Vencimiento
            except SoapFault as fault:
                msg = 'Falla SOAP %s: %s' % (
                    fault.faultcode, fault.faultstring)
            except Exception as e:
                msg = e
            except Exception:
                if ws.Excepcion:
                    # get the exception already parsed by the helper
                    msg = ws.Excepcion
                else:
                    # avoid encoding problem when raising error
                    msg = traceback.format_exception_only(
                        sys.exc_type,
                        sys.exc_value)[0]
            if msg:
                _logger.info(_('AFIP Validation Error. %s' % msg)+' XML Request: %s XML Response: %s' % (
                    ws.XmlRequest, ws.XmlResponse))
                raise UserError(_('AFIP Validation Error. %s' % msg))

            msg = u"\n".join([ws.Obs or "", ws.ErrMsg or ""])
            if not ws.CAE or ws.Resultado != 'A':
                _logger.info('XmlRequest: %s\n\XmlResponse %s' % (ws.XmlRequest, ws.XmlResponse))
                raise UserError(_('AFIP Validation Error. %s' % msg))
            # TODO ver que algunso campos no tienen sentido porque solo se
            # escribe aca si no hay errores
            _logger.info('CAE solicitado con exito. CAE: %s. Resultado %s' % (
                ws.CAE, ws.Resultado))
            if afip_ws == 'wsbfe':
                vto = datetime.strftime(
                    datetime.strptime(vto, '%d/%m/%Y'), '%Y%m%d')
            inv.write({
                'afip_auth_mode': 'CAE',
                'afip_auth_code': ws.CAE,
                'afip_auth_code_due': vto,
                'afip_result': ws.Resultado,
                'afip_message': msg,
                'afip_xml_request': ws.XmlRequest,
                'afip_xml_response': ws.XmlResponse,
            })
            # si obtuvimos el cae hacemos el commit porque estoya no se puede
            # volver atras
            # otra alternativa seria escribir con otro cursor el cae y que
            # la factura no quede validada total si tiene cae no se vuelve a
            # solicitar. Lo mismo podriamos usar para grabar los mensajes de
            # afip de respuesta
            inv._cr.commit()



    # # Metodo sobreescripto
    # def wsfe_pyafipws_create_invoice(self, ws, invoice_info):
    #     ws.CrearFactura(
    #         invoice_info["concepto"],
    #         invoice_info["tipo_doc"],
    #         invoice_info["nro_doc"],
    #         invoice_info["doc_afip_code"],
    #         invoice_info["pos_number"],
    #         invoice_info["cbt_desde"],
    #         invoice_info["cbt_hasta"],
    #         invoice_info["imp_total"],
    #         invoice_info["imp_tot_conc"],
    #         invoice_info["imp_neto"],
    #         invoice_info["imp_iva"],
    #         invoice_info["imp_trib"],
    #         invoice_info["imp_op_ex"],
    #         invoice_info["fecha_cbte"],
    #         invoice_info["fecha_venc_pago"],
    #         invoice_info["fecha_serv_desde"],
    #         invoice_info["fecha_serv_hasta"],
    #         invoice_info["moneda_id"],
    #         invoice_info["moneda_ctz"],
    #         cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
    #         condicion_iva_receptor_id=invoice_info["condicion_iva_receptor_id"],
    #     )

    # def wsmtxca_pyafipws_create_invoice(self, ws, invoice_info):
    #     ws.CrearFactura(
    #         invoice_info["concepto"],
    #         invoice_info["tipo_doc"],
    #         invoice_info["nro_doc"],
    #         invoice_info["doc_afip_code"],
    #         invoice_info["pos_number"],
    #         invoice_info["cbt_desde"],
    #         invoice_info["cbt_hasta"],
    #         invoice_info["imp_total"],
    #         invoice_info["imp_tot_conc"],
    #         invoice_info["imp_neto"],
    #         invoice_info["imp_subtotal"],
    #         invoice_info["imp_trib"],
    #         invoice_info["imp_op_ex"],
    #         invoice_info["fecha_cbte"],
    #         invoice_info["fecha_venc_pago"],
    #         invoice_info["fecha_serv_desde"],
    #         invoice_info["fecha_serv_hasta"],
    #         invoice_info["moneda_id"],
    #         invoice_info["moneda_ctz"],
    #         invoice_info["obs_generales"],
    #         cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
    #         condicion_iva_receptor_id=invoice_info["condicion_iva_receptor_id"],
    #     )

    # def wsfex_pyafipws_create_invoice(self, ws, invoice_info):
    #     ws.CrearFactura(
    #         invoice_info["doc_afip_code"],
    #         invoice_info["pos_number"],
    #         invoice_info["cbte_nro"],
    #         invoice_info["fecha_cbte"],
    #         invoice_info["imp_total"],
    #         invoice_info["tipo_expo"],
    #         invoice_info["permiso_existente"],
    #         invoice_info["pais_dst_cmp"],
    #         invoice_info["nombre_cliente"],
    #         invoice_info["cuit_pais_cliente"],
    #         invoice_info["domicilio_cliente"],
    #         invoice_info["id_impositivo"],
    #         invoice_info["moneda_id"],
    #         invoice_info["moneda_ctz"],
    #         invoice_info["obs_comerciales"],
    #         invoice_info["obs_generales"],
    #         invoice_info["forma_pago"],
    #         invoice_info["incoterms"],
    #         invoice_info["idioma_cbte"],
    #         invoice_info["incoterms_ds"],
    #         invoice_info["fecha_pago"],
    #         cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
    #         condicion_iva_receptor_id=invoice_info["condicion_iva_receptor_id"],
    #     )

    # def wsbfe_pyafipws_create_invoice(self, ws, invoice_info):
    #     ws.CrearFactura(
    #         invoice_info["tipo_doc"],
    #         invoice_info["nro_doc"],
    #         invoice_info["zona"],
    #         invoice_info["doc_afip_code"],
    #         invoice_info["pos_number"],
    #         invoice_info["cbte_nro"],
    #         invoice_info["fecha_cbte"],
    #         invoice_info["imp_total"],
    #         invoice_info["imp_neto"],
    #         invoice_info["imp_iva"],
    #         invoice_info["imp_tot_conc"],
    #         invoice_info["impto_liq_rni"],
    #         invoice_info["imp_op_ex"],
    #         invoice_info["imp_perc"],
    #         invoice_info["imp_iibb"],
    #         invoice_info["imp_perc_mun"],
    #         invoice_info["imp_internos"],
    #         invoice_info["moneda_id"],
    #         invoice_info["moneda_ctz"],
    #         invoice_info["fecha_venc_pago"],
    #         cancela_misma_moneda_ext=invoice_info["cancela_misma_moneda_ext"],
    #         condicion_iva_receptor_id=invoice_info["condicion_iva_receptor_id"],
    #     )

    # def base_map_invoice_info(self):
    #     invoice_info = super().base_map_invoice_info()

    #     invoice_info["cancela_misma_moneda_ext"] = self.l10n_ar_payment_foreign_currency
    #     invoice_info["condicion_iva_receptor_id"] = self.partner_id.l10n_ar_afip_responsibility_type_id.code

    #     return invoice_info

    # def pyafipws_get_currency_rate(self, ws):
    #     self.ensure_one()
    #     afip_ws = self.journal_id.afip_ws
    #     if not afip_ws:
    #         return
    #     if hasattr(self, "%s_pyafipws_get_currency_rate" % afip_ws):
    #         return getattr(self, "%s_pyafipws_get_currency_rate" % afip_ws)(
    #             ws
    #         )
    #     else:
    #         return _("AFIP WS %s not implemented") % afip_ws

    # def pyafipws_get_currency_rate(self, ws):
    #     return ws.ParamGetCotizacion(self.currency_id.l10n_ar_afip_code)

    
