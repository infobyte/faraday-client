"""
Faraday Penetration Test IDE
Copyright (C) 2017  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
from __future__ import absolute_import
from __future__ import print_function

from time import time
from json import load
from faraday_client.model.common import factory
from faraday_client.persistence.server import models, server


__description__ = "Creates a new executive report in current workspace"
__prettyname__ = "Create executive report"


def main(workspace="", args=None, parser=None):

    parser.add_argument("--report-name", help="Report name", default="")
    parser.add_argument("--tags", help="Tags (separated by space)", default=[], nargs="+")
    parser.add_argument("--title", help="Title", default="")
    parser.add_argument("--enterprise", help="Enterprise", default="")
    parser.add_argument("--scope", help="Scope", default="")
    parser.add_argument("--objectives", help="Objectives", default="")
    parser.add_argument("--summary", help="Summary", default="")
    parser.add_argument("--only-confirmed", help="Only confirmed vulnerabilities", action="store_true")
    parser.add_argument("--template-name", help="Template name", default="generic_default.docx")
    parser.add_argument("--conclusions", help="Conclusions", default="")
    parser.add_argument("--recommendations", help="Recommendations", default="")
    parser.add_argument("--owner", help="Owner", default="")
    parser.add_argument("--use-grouped", help="Use grouped report type", action="store_true")

    parser.add_argument("--download", action="store_true", help="Download report")
    parser.add_argument("--download-path", help="Path complete for download executive report (name, title, enterprise, scope, objectives, summary, conclusions, recommendations)", default="./Report.docx")
    parser.add_argument("--json-load", help="Load fields of report from Json", default="")

    parsed_args = parser.parse_args(args)

    print("Count of vulns in executive report:")
    count = server.get_report_count_vulns(workspace, parsed_args.only_confirmed, parsed_args.tags)

    for key, val in count.items():
        print(key, ":", val)

    data = {}
    if parsed_args.json_load:
        try:

            with open(parsed_args.json_load) as data_file:
                data = load(data_file)
        except Exception as e:
            print("Error loading JSON file. Abort fplugin")
            print(e)
            return 2, None

    if not parsed_args.template_name.startswith("group_") and parsed_args.use_grouped:
        print("Error: You need use a grouped template if you use --use-grouped")
        return 3, None

    obj_report = factory.createModelObject(
        models.Report.class_signature,
        parsed_args.report_name,
        workspace_name=workspace,
        parent_id=None,
        name=data.get("name") if data.get("name") else parsed_args.report_name,
        tags=parsed_args.tags,
        title=data.get("title") if data.get("title") else parsed_args.title,
        enterprise=data.get("enterprise") if data.get("enterprise") else parsed_args.enterprise,
        scope=data.get("scope") if data.get("scope") else parsed_args.scope,
        objectives=data.get("objectives") if data.get("objectives") else parsed_args.objectives,
        summary=data.get("summary") if data.get("summary") else parsed_args.summary,
        confirmed=parsed_args.only_confirmed,
        template_name=parsed_args.template_name,
        conclusions=data.get("conclusions") if data.get("conclusions") else  parsed_args.conclusions,
        recommendations=data.get("recommendations") if data.get("recommendations") else parsed_args.recommendations,
        date=int(time() * 1000),
        owner=parsed_args.owner,
        grouped=parsed_args.use_grouped)

    report = models.create_report(workspace, obj_report)
    print("\nNew report created!")
    print("ID: " + str(report.get("id")))

    if parsed_args.download:
        response = server.get_report_docx(workspace, report.get("id"))

        with open(parsed_args.download_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        print("\nDownload ready: " + parsed_args.download_path)

    return 0, None


# I'm Py3
