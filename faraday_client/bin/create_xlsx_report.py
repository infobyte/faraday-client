#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
Faraday Penetration Test IDE
Copyright (C) 2018  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from __future__ import absolute_import
from __future__ import print_function
import os
import re
import sys
import datetime
import json

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

from requests import Session
from tqdm import tqdm

from faraday_client.persistence.server import models

__description__ = 'Creates a xls report from current workspace'
__prettyname__ = 'Create XLS Report'


def init_template(workbook, worksheet):
    # Constants
    pink_color = '#FF99CC'
    cyan_color = '#CCFFFF'
    green_color = '#CCFFCC'
    blue_color = '#99CCFF'
    width_2 = 2
    width_5 = 5
    width_10 = 10
    width_15 = 15
    width_20 = 20
    width_25 = 25

    height_25 = 25

    # Formats
    bg_pink_format = set_format(workbook, 'bg', bg_color=pink_color)
    rotation_pink_format = set_format(workbook, 'rotation',bg_color=pink_color)
    header_pink_format = set_format(workbook, 'header', bg_color=pink_color)

    bg_cyan_format = set_format(workbook, 'bg', bg_color=cyan_color)
    rotation_cyan_format = set_format(workbook, 'rotation', bg_color=cyan_color)
    header_cyan_format = set_format(workbook, 'header', bg_color=cyan_color)

    bg_green_format = set_format(workbook, 'bg', bg_color=green_color)
    rotation_green_format = set_format(workbook, 'rotation', bg_color=green_color)
    header_green_format = set_format(workbook, 'header', bg_color=green_color)

    bg_blue_format = set_format(workbook, 'bg', bg_color=blue_color)
    rotation_blue_format = set_format(workbook, 'rotation', bg_color=blue_color)
    header_blue_format = set_format(workbook, 'header', bg_color=blue_color)

    worksheet.set_row(0, height_25)
    worksheet.set_row(1, height_25)

    # Writting pink
    worksheet.merge_range('B1:M1', 'Vulnerability Data', bg_pink_format)
    worksheet.set_column('A:A', width_2)
    worksheet.merge_range('A1:A2', 'Vuln-Data', rotation_pink_format)
    worksheet.set_column('B:B', width_5)
    worksheet.write('B2', 'No.', header_pink_format)
    worksheet.set_column('C:C', width_10)
    worksheet.write('C2', 'Date', header_pink_format)
    worksheet.set_column('D:D', width_25)
    worksheet.write('D2', 'Title', header_pink_format)
    worksheet.set_column('E:E', width_25)
    worksheet.write('E2', 'Affected System', header_pink_format)
    worksheet.set_column('F:F', width_25)
    worksheet.write('F2', 'Vulnerability', header_pink_format)
    worksheet.set_column('G:G', width_25)
    worksheet.write('G2', 'Impact', header_pink_format)
    worksheet.set_column('H:H', width_25)
    worksheet.write('H2', 'Action/Measure', header_pink_format)
    worksheet.set_column('I:I', width_15)
    worksheet.write('I2', 'Risk', header_pink_format)
    worksheet.set_column('J:J', width_15)
    worksheet.write('J2', 'Ease of resolution', header_pink_format)
    worksheet.set_column('K:K', width_25)
    worksheet.write('K2', 'Status', header_pink_format)
    worksheet.set_column('L:L', width_25)
    worksheet.write('L2', 'Remarks', header_pink_format)
    worksheet.set_column('M:M', width_25)
    worksheet.write('M2', 'Requirement/Reference', header_pink_format)

    # Writting cyan
    worksheet.merge_range('O1:Q1', 'Vulnerability Category', bg_cyan_format)
    worksheet.set_column('N:N', width_2)
    worksheet.merge_range('N1:N2', 'Vuln-Category', rotation_cyan_format)
    worksheet.set_column('O:O', width_25)
    worksheet.write('O2', 'Category', header_cyan_format)
    worksheet.set_column('P:P', width_25)
    worksheet.write('P2', 'Subcategory', header_cyan_format)
    worksheet.set_column('Q:Q', width_25)
    worksheet.write('Q2', '2nd Subcategory', header_cyan_format)

    # Writting green
    worksheet.write('S1', 'Monitoring', bg_green_format)
    worksheet.set_column('R:R', width_2)
    worksheet.merge_range('R1:R2', 'Monitoring', rotation_green_format)
    worksheet.set_column('S:S', width_25)
    worksheet.write('S2', 'Status Monitoring', header_green_format)

    # Writting blue
    worksheet.write('U1', '', bg_blue_format)
    worksheet.set_column('T:T', width_2)
    worksheet.merge_range('T1:T2', 'Process', rotation_blue_format)
    worksheet.set_column('U:U', width_10)
    worksheet.write('U2', 'Report?', header_blue_format)

    # Writting green
    bg_green_format.set_right(True)
    worksheet.merge_range('W1:Y1', 'CVSS', bg_green_format)
    worksheet.set_column('V:V', width_2)
    worksheet.merge_range('V1:V2', 'CVSS', rotation_green_format)
    worksheet.set_column('W:W', width_20)
    worksheet.write('W2', 'CVSS Vector', header_green_format)
    worksheet.set_column('X:X', width_20)
    worksheet.write('X2', 'CVSS Version', header_green_format)
    worksheet.set_column('Y:Y', width_20)
    worksheet.write('Y2', 'CVSS Score', header_green_format)

# Set workbook format
def set_format(workbook, aux, **kwargs):
    if aux == 'bg':
        kwargs.update({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bottom': True,
            'font_size': '16'
        })
    elif aux == 'rotation':
        kwargs.update({
            'rotation': '90',
            'bottom': True,
            'font_size': '10',
            'bold': True,
        })
    elif aux == 'header':
        kwargs.update({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': True,
            'font_size': '10'
        })
    elif aux == 'standard':
        kwargs.update({
            'font_name': 'Arial',
            'font_color': 'black'
        })

    return workbook.add_format(kwargs)

# Set background color
def color_format(workbook, **kwargs):
    wb_dict = {
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Arial',
            'font_size': '10',
            'text_wrap': 1,
        }

    wb_dict.update(kwargs)

    return workbook.add_format(wb_dict)

# Get data from severity and ease of resolution
def get_data_from_vuln(workbook, vuln):
    data = vuln
    color = None
    if data in ['info','simple']:
        color = color_format(workbook, bg_color='#2e97bd')
    elif data in ['low','trivial']:
        color = color_format(workbook, bg_color='#a1ce31')
    elif data in ['med', 'moderate']:
        color = color_format(workbook, bg_color='#dfbf35')
    elif data in ['high', 'difficult']:
        color = color_format(workbook, bg_color='#df3936')
    elif data in ['critical', 'infeasible']:
        color = color_format(workbook, bg_color='#932ebe')
    elif data=='unclassified':
        color = color_format(workbook, bg_color='#999999')
    elif not data:
        data = ''
        color = color_format(workbook, bg_color='#999999')

    return data.capitalize(), color

# Patch possible formula injection attacks
def csv_escape(vuln_dict):
    for key,value in vuln_dict.items():
        if str(value).startswith('=') or str(value).startswith('+') or str(value).startswith('-') or str(value).startswith('@'):
            vuln_dict[key] = "'" + value

    return vuln_dict

def main(workspace='', args=None, parser=None):
    if not xlsxwriter:
        print('ImportError: XlsxWriter is not installed. Please install it by running: pip install xlsxwriter')
        return 0, None

    session = Session()
    session.post(models.server.SERVER_URL + '/_api/login', json={'email': models.server.AUTH_USER, 'password': models.server.AUTH_PASS})
    vulns = session.get(models.server.SERVER_URL + '/_api/v2/ws/' + workspace + '/vulns')

    parser.add_argument('-o', '--output', help='Output xlsx file report', required=True)
    parsed_args = parser.parse_args(args)
    xls_output_file = parsed_args.output

    try:
        # Create a workbook and add a worksheet.
        # TODO: Create folders recursively
        dir_name = os.path.dirname(xls_output_file)
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)

        workbook = xlsxwriter.Workbook(xls_output_file)
        worksheet = workbook.add_worksheet()

        init_template(workbook, worksheet)

        content_center_format = set_format(workbook, 'standard', align='center', valign='vcenter' , font_size='10', text_wrap=1)
        content_format = set_format(workbook, 'standard', valign='vcenter' , font_size='10', text_wrap=1)

        row = 2

        vulns_dict = json.loads(vulns.content)
        with tqdm(total=vulns_dict['count']) as pbar:
            for index, value in enumerate(vulns_dict['vulnerabilities']):
                vuln = csv_escape(value['value'])
                # Writing order
                worksheet.write(row, 1, index + 1, content_center_format)
                # Writing date
                now = datetime.datetime.now()
                worksheet.write(row, 2, now.strftime("%d.%m.%Y"), content_center_format)
                # Writing title
                worksheet.write(row, 3, vuln['name'], content_format)

                # Writing System
                if vuln['hostnames']:
                    hostnames = ", ".join(vuln['hostnames'])
                    affected_system = "{target}. [{hostname}]".format(target=vuln['target'], hostname=hostnames)
                else:
                    affected_system = vuln['target']
                worksheet.write(row, 4, affected_system, content_center_format)

                # Writing vulnerability
                worksheet.write(row, 5, vuln['desc'], content_format)  # Writing vulnerability

                # Writing Impact
                impact_list = []
                if vuln['impact']['integrity']:
                    impact_list.append('Integrity')
                if vuln['impact']['availability']:
                    impact_list.append('Availability')
                if vuln['impact']['accountability']:
                    impact_list.append('Accountability')
                if vuln['impact']['confidentiality']:
                    impact_list.append('Confidentiality')
                impact = ', '.join(impact_list)

                worksheet.write(row, 6, impact, content_center_format)

                # Writing Action/Measure
                worksheet.write(row, 7, vuln['resolution'], content_center_format)

                # Writing Risk
                severity = get_data_from_vuln(workbook, vuln['severity'])
                worksheet.write(row, 8, severity[0], severity[1])

                # Writing Ease of Resolution
                ease = get_data_from_vuln(workbook, vuln['easeofresolution'])
                worksheet.write(row, 9, ease[0], ease[1])

                # Writing Status (vuln confimed/unconfirmed)
                confirmed = 'Unconfirmed'
                cformat = color_format(workbook, bg_color='#c0c0c0')
                if vuln['confirmed']:
                    confirmed = 'Confirmed'
                    cformat = color_format(workbook, bg_color='#2e97bd')
                worksheet.write(row, 10, confirmed, cformat)

                # Writing remarks
                worksheet.write(row, 11, vuln['data'], content_center_format)

                # Writing refs
                refs = ''

                for ref in vuln['refs']:
                    if 'cvss' in ref.lower():
                        # CVSS Section
                        regex_vector = re.compile(
                            r'(cvssvector(-))')
                        regex_score = re.compile(
                            r'((cvss( *)score(-|:| *))|(cvss: (\d\.\d|\d\d\.\d|\d\d|\d)))')

                        if regex_vector.match(ref.lower()):
                            # Writing CVSS Vector and CVSS Version
                            vector_v2 = re.findall(
                                r"AV:[NAL]\/AC:[LMH]\/A[Uu]:[NSM]\/C:[NPC]\/I:[NPC]\/A:[NPC]", ref)
                            if vector_v2:
                                # CVSS Version 2
                                worksheet.write(row, 22, vector_v2[0], content_center_format)
                                worksheet.write(row, 23, 'V2', content_center_format)
                            else:
                                # CVSS Version 3
                                vector_v3 = re.findall(
                                    r"AV:[NALP]\/AC:[LH]\/PR:[NLH]\/UI:[NR]\/S:[UC]\/C:[NLH]\/I:[NLH]\/A:[NLH]", ref)
                                worksheet.write(row, 22, vector_v3[0], content_center_format)
                                worksheet.write(row, 23, 'V3', content_center_format)
                        if regex_score.match(ref.lower()):
                            # Writing CVSS Score
                            score = re.findall(r"\d\.\d|\d\d\.\d|\d\d|\d", ref)
                            worksheet.write(row, 24, score[0], content_center_format)
                    else:
                        refs += ref + '\n'

                worksheet.write(row, 12, refs, content_format)

                # Writing vulnerability category if vulnerability
                if vuln['type']  == 'Vulnerability':
                    worksheet.write(row, 14, 'Infrastructure', content_center_format)
                else:
                    # Writing vulnerability categoty if vuln web
                    worksheet.write(row, 14, 'Application', content_center_format)

                # Writing monitoring (vuln status)
                worksheet.write(row, 18, vuln['status'], content_center_format)

                row += 1
                pbar.update(1)

            workbook.close()

    except (IOError, OSError):
        print("ERROR: '{0}' doesn't exist".format(xls_output_file))

    return 0, None


# I'm Py3
