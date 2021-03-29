# -*- encoding: utf-8 -*-
################################################################################
#
#  This file is part of Aeroo Reports software - for license refer LICENSE file
#
################################################################################

import logging
from io import BytesIO
from PIL import Image
from base64 import b64decode
import time
import base64
from aeroolib.plugins.opendocument import Template, OOSerializer, _filter
from aeroolib import __version__ as aeroolib_version
from currency2text import supported_language, currency_to_text

from genshi.template.eval import StrictLookup

from odoo import release as odoo_release
from odoo import api, models, fields
from odoo.tools import file_open, frozendict
from odoo.tools.translate import _, translate
from odoo.tools.misc import formatLang as odoo_fl
from odoo.tools.misc import format_date as odoo_fd
from odoo.tools.safe_eval import safe_eval
from odoo.modules import load_information_from_description_file
from odoo.exceptions import MissingError


_logger = logging.getLogger(__name__)

mime_dict = {'oo-odt': 'odt',
             'oo-ods': 'ods',
             'oo-pdf': 'pdf',
             'oo-doc': 'doc',
             'oo-xls': 'xls',
             'oo-csv': 'csv',
             }


class ReportAerooAbstract(models.AbstractModel):

    _inherit = 'report.report_aeroo.abstract'
    _name = 'report.report_aeroo.abstract'



    def _calcule_quantity_sum(self, line_obj,var_control_name, var_control_length,var_control_first_double):
        expr = "summ = len(o.%s)" % var_control_name
        localspace = {'o':line_obj, 'summ':0}
        exec(expr, localspace)
        aux = localspace['summ']
        var_return = 0 
        while aux > 0:
            var_return +=1
            summ = var_control_length
            if var_return==0 and var_control_first_double:
                summ = summ+summ
            aux -=summ
        return var_return


    def _add_page(self,list_page, list_page_line,aux,quantity_copie,previus_list_page,complete_list=''):

        if quantity_copie >= 1:
            page = {'line_ids' :list_page_line,'number_of_page':aux,'new_page':1, 
                    'name_copie':'ORIGINAL','previus_list_page':previus_list_page,'complete_list':complete_list}
            list_page.append(page)
        if quantity_copie >= 2:
            page = {'line_ids' :list_page_line,'number_of_page':aux,'new_page':1,
                    'name_copie':'DUPLICADO','previus_list_page':previus_list_page,'complete_list':complete_list}
            list_page.append(page)
        if quantity_copie >= 3:
            page = {'line_ids' :list_page_line,'number_of_page':aux,'new_page':1,
                    'name_copie':'TRIPLICADO','previus_list_page':previus_list_page,'complete_list':complete_list}
            list_page.append(page)
        return list_page

    def _get_report_page(self,line_ids,quantity_line,var_control_name=None, var_control_length=1,var_control_first_double=False,quantity_copie=1):
        ################
        # Este metodo arma las paginas para poder armar listas con determinada cantidad de registros en el reporte
        #   PARAMETROS:
        #   line_ids: que son los registros correspondientes que iran en la lista (el total de los registros)
        #   quantity_line: cantidad de lineas que va a poseer cada pagina
        #   var_control_name y var_control_length : controlan si un registro "ocupa" mas de una linea o no,
        #       en el caso de que la Descripcion sea larga se debera de mandar "var_control_name:'Descripcion'" y en
        #       "var_control_length:50".. esto indica que va a controlar la Descripcion con 50 caracteres, si tiene 51,
        #       2 lineas.. si tiene 101, 3 lineas y asi sucesivamente 
        #   quantity_copie: 1 para solo original, 2 para original y duplicado y 3 para original, duplicado y triplicado
        ################
        #   DEVUELVE:
        #   una coleccion de paginas que cada contiene:
        #       'line_ids' :objetos de la pagina a procesar
        #       'number_of_page': numero de objetos de la pagina
        #       'new_page': 1 cuando hay una pagina mas por venir y 0 cuando es la ultima pagina (se utiliza para el salto de pagina)
        #       'name_copie': nombre de la copia 'ORIGINAL','DUPLICADO' o 'TRIPLICADO'
        #       'previus_list_page': lista de lista de objetos de las paginas anteriores (para un subtotal)
        ################
        list_page = []
        previus_list_page = []
        list_page_line = []
        aux = 1
        quantity_sum = 1
        for line_obj in line_ids:
            if var_control_name:
                quantity_sum = self._calcule_quantity_sum(line_obj,var_control_name, var_control_length,var_control_first_double)
            if aux < quantity_line:
                list_page_line.append(line_obj)
                aux += quantity_sum
            else:
                list_page_line.append(line_obj)
                previus_list_page.append(list_page_line)

                list_page = self._add_page(list_page,list_page_line,aux, quantity_copie,previus_list_page)
                previus_list_page = previus_list_page.copy()
                list_page_line = []
                aux = 1
        if aux != 1:
            previus_list_page.append(list_page_line)
            diff = quantity_line-aux
            complete_list = ''
            while diff!=0:
                diff -=1
                complete_list += '\n'
                if var_control_first_double:
                    complete_list += '\n'
            list_page = self._add_page(list_page,list_page_line,aux, quantity_copie,previus_list_page,complete_list=complete_list)
        # saca el salto de pagina de la ultima hoja
        list_page[len(list_page)-1]['new_page'] = 0
        return list_page


    def _get_subtotal(self, previus_list_page,var_name):
        ##################
        # este metodo recibe las lineas de la pagina y las anteriores y devuelve la suma de la  columna pasada como parametor en var_name
        ##################
        amount_return = 0.0
        for page in previus_list_page:
            for line_obj in page:
                #amount_return += line_obj.price_subtotal
                expr = "value = o.%s" % var_name
                localspace = {'o':line_obj, 'value':0}
                exec(expr, localspace)
                amount_return += localspace['value']
        return amount_return


### SACAR ESTE METODO

    def complex_report(self, docids, data, report, ctx):
        """ Returns an aeroo report generated by aeroolib
        """
        self.model = ctx.get('active_model', False)
        # tmpl_type = 'odt'
        self.record_ids = docids
        self.ctx = ctx
        self.company = self.env.user.company_id
        self.report = report

        #=======================================================================
        def barcode(
                barcode_type, value, width=600, height=100, humanreadable=0):
            # TODO check that asimage and barcode both accepts width and height
            img = self.env['ir.actions.report'].barcode(
                barcode_type, value, width=width, height=height,
                humanreadable=humanreadable)
            return self._asimage(base64.b64encode(img))
        self.localcontext = {
            'user':     self.env.user,
            'user_lang': ctx.get('lang', False),
            'data':     data,


# unica linea que se agrega
'get_report_page': self._get_report_page ,
'get_subtotal': self._get_subtotal ,
# unica linea que se agrega


            'time':     time,
            'asarray':  self._asarray,
            'average':  self._average,
            'currency_to_text': self._currency_to_text,
            'asimage': self._asimage,
            'get_selection_item': self._get_selection_items('item'),
            'get_selection_items': self._get_selection_items(),
            'get_log': self._get_log,
            'asarray': self._asarray,

            '__filter': self.__filter,  # Don't use in the report template!
            'getLang':  self._get_lang,
            'setLang':  self._set_lang,
            'formatLang': self._format_lang,
            '_': self._translate_text,
            'gettext': self._translate_text,
            'test':     self.test,
            'fields':     fields,
            'company':     self.env.user.company_id,
            'barcode':     barcode,
        }
        self.localcontext.update(ctx)
        self._set_lang(self.company.partner_id.lang)
        self._set_objects(self.model, docids)

        file_data = None
        if report.tml_source == 'database':
            if not report.report_data or report.report_data == 'False':
                # TODO log report ID etc.
                raise MissingError(
                    _("Aeroo Reports could'nt find report template"))
            file_data = b64decode(report.report_data)
        elif report.tml_source == 'file':
            if not report.report_file or report.report_file == 'False':
                # TODO log report ID etc.
                raise MissingError(
                    _("No Aeroo Reports template filename provided"))
            file_data = report._read_template()
        else:
            rec_id = ctx.get('active_id', data.get('id')) or data.get('id')
            file_data = self.get_other_template(self.model, rec_id)

        if not file_data:
            # TODO log report ID etc.
            raise MissingError(_("Aeroo Reports could'nt find report template"))

        template_io = BytesIO(file_data)
        if report.styles_mode == 'default':
            serializer = OOSerializer(template_io)
        else:
            style_io = BytesIO(self.get_stylesheet(report))
            serializer = OOSerializer(template_io, oo_styles=style_io)

        basic = Template(source=template_io,
                         serializer=serializer,
                         lookup=StrictLookup
                         )

        # Add metadata
        ser = basic.Serializer
        model_obj = self.env.get('ir.model')
        model_name = model_obj.search([('model', '=', self.model)])[0].name
        ser.add_title(model_name)

        user_name = self.env.user.name
        ser.add_creation_user(user_name)

        module_info = load_information_from_description_file('report_aeroo')
        version = module_info['version']
        ser.add_generator_info('Aeroo Lib/%s Aeroo Reports/%s'
                               % (aeroolib_version, version))
        ser.add_custom_property('Aeroo Reports %s' % version, 'Generator')
        ser.add_custom_property('Odoo %s' % odoo_release.version, 'Software')
        ser.add_custom_property(module_info['website'], 'URL')
        ser.add_creation_date(time.strftime('%Y-%m-%dT%H:%M:%S'))

## ACA CONTROLA SI ESTAN O NO LOS METODOS Y TIRA ERROR hay que sobreescribir el metodo si o si ..
## ACA CONTROLA SI ESTAN O NO LOS METODOS Y TIRA ERROR hay que sobreescribir el metodo si o si ..
        file_data = basic.generate(**self.localcontext).render().getvalue()
        #=======================================================================
        code = mime_dict[report.in_format]
        #_logger.info("End process %s (%s), elapsed time: %s" % (self.name, self.model, time.time() - aeroo_print.start_time), logging.INFO) # debug mode


        return file_data, code











