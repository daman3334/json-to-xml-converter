from flask import Flask, request, render_template_string, send_file
import json
import xml.etree.ElementTree as ET
import xml.dom.minidom
import io
import os

app = Flask(__name__)

# Map official DayZ slot names to our internal sorting
OFFICIAL_TO_INTERNAL = {
    "hips": "belt",
    "feet": "boots"
}

def map_slot(slot_name):
    return OFFICIAL_TO_INTERNAL.get(slot_name.lower(), slot_name)

def get_major_priority(slot_name, item_name):
    s = slot_name.lower()
    i = item_name.lower()

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

def belt_priority(item_name):
    i = item_name.lower()
    if "belt" in i:
        return 0
    if "canteen" in i:
        return 1
    if "nylonknifesheath" in i:
        return 2
    if "knife" in i:
        return 3
    if "holster" in i:
        return 4
    if any(x in i for x in ["glock", "colt", "pistol", "fnx", "deagle"]):
        return 5
    if "optic" in i:
        return 6
    if "mag_" in i:
        return 7
    if "pistolsuppressor" in i:
        return 8
    return 9

def vest_priority(item_name):
    i = item_name.lower()
    if "platecarriervest" in i:
        return 0
    if "platecarrierpouches" in i:
        return 1
    if "flashgrenade" in i:
        return 2
    if any(x in i for x in ["glock", "colt", "pistol", "fnx", "deagle"]):
        return 3
    if "optic" in i:
        return 4
    if "mag_" in i:
        return 5
    if "pistolsuppressor" in i:
        return 6
    if "holster" in i:
        return 7
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
        major = get_major_priority(entry["slot"], entry["item"])
        minor = 0
        if major == 5:
            minor = belt_priority(entry["item"])
        elif major == 6:
            minor = vest_priority(entry["item"])
        return (major, minor)

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
        if "file" not in request.files:
            return "No file uploaded"
        
        file = request.files["file"]
        if file.filename == "":
            return "No selected file"
        
        try:
            json_data = json.load(file)
            xml_output = convert_json_to_xml(json_data)
            
            return render_template_string("""
                <h2>XML Preview</h2>
                <pre>{{ xml_output }}</pre>
                <a href="/download?xml={{ xml_output | urlencode }}">Download XML</a>
                <br><br>
                <a href="/">Upload another file</a>
            """, xml_output=xml_output)
        except Exception as e:
            return f"Error processing file: {str(e)}"

    return render_template_string('''
        <h1>Upload JSON File</h1>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="Convert to XML">
        </form>
    ''')

@app.route("/download")
def download_file():
    xml_content = request.args.get("xml", "")
    
    if not xml_content:
        return "No XML content to download"
    
    xml_file = io.BytesIO(xml_content.encode("utf-8"))
    xml_file.seek(0)
    
    return send_file(xml_file, as_attachment=True, download_name="output.xml", mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
