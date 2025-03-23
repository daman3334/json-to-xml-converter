from flask import Flask, request, render_template, send_file, session
import json
import xml.etree.ElementTree as ET
import xml.dom.minidom
import io
import os
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "replace-with-a-secret-key"

OFFICIAL_TO_INTERNAL = {
    "hips": "belt",
    "feet": "boots"
}

def map_slot(slot_name):
    return OFFICIAL_TO_INTERNAL.get(slot_name.lower(), slot_name)

def get_major_priority(slot_name, item_name):
    s = slot_name.lower()
    i = item_name.lower()

    if s == "hands":
        return -1
    if any(x in s for x in ["helmet", "face", "mask", "eyewear", "headgear"]) or any(x in i for x in ["helmet", "nvg", "balaclava", "hat", "goggles"]):
        return 0
    if s == "shoulderl":
        return 1
    if s == "shoulderr":
        return 2
    if s == "gloves":
        return 3
    if s == "boots":
        return 4
    if s == "belt":
        return 5
    if s == "vest":
        return 6
    if s == "body" or s == "legs":
        return 7
    if s == "back":
        return 8
    return 9

def gather_items(item_set, slot_name, accumulator):
    main_item = item_set["itemType"]
    accumulator.append({"slot": slot_name, "item": main_item})
    for child in item_set.get("simpleChildrenTypes", []):
        accumulator.append({"slot": slot_name, "item": child})
    for complex_child in item_set.get("complexChildrenTypes", []):
        gather_items(complex_child, slot_name, accumulator)

def convert_json_to_xml(json_data):
    root = ET.Element("type", name=json_data["name"])
    items_list = []

    for slot_data in json_data.get("attachmentSlotItemSets", []):
        mapped_slot = map_slot(slot_data["slotName"])
        for item_set in slot_data["discreteItemSets"]:
            gather_items(item_set, mapped_slot, items_list)

    for unsorted_set in json_data.get("discreteUnsortedItemSets", []):
        for item_name in unsorted_set.get("simpleChildrenTypes", []):
            items_list.append({"slot": "back", "item": item_name})

    def sort_key(entry):
        return (get_major_priority(entry["slot"], entry["item"]), 0)

    items_list.sort(key=sort_key)

    for entry in items_list:
        block = ET.SubElement(root, "attachments", chance="1")
        ET.SubElement(block, "item", name=entry["item"], chance="1.00")

    rough_string = ET.tostring(root, encoding="utf-8", method="xml")
    reparsed = xml.dom.minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("error.html", message="Upload error. Please select a file.")

        try:
            if file.read(1) == b"":
                return render_template("error.html", message="Empty file. Please upload a valid JSON file.")
            file.seek(0)
            json_data = json.load(file)

            if "name" not in json_data:
                return render_template("error.html", message="Missing 'name' field in JSON.")

            xml_output = convert_json_to_xml(json_data)

            history = session.get("history", [])
            history.append({"filename": file.filename, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            session["history"] = history[-5:]

            return render_template("result.html", xml_output=xml_output)

        except json.JSONDecodeError:
            return render_template("error.html", message="Invalid JSON format.")

        except Exception as e:
            return render_template("error.html", message=f"Unexpected error: {str(e)}")

    history = session.get("history", [])
    return render_template("upload.html", history=history)

@app.route("/download")
def download_file():
    xml_content = request.args.get("xml", "")
    if not xml_content:
        return "No XML to download"
    xml_file = io.BytesIO(xml_content.encode("utf-8"))
    xml_file.seek(0)
    return send_file(xml_file, as_attachment=True, download_name="output.xml", mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
