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

    # HANDS (Highest Priority)
    if s == "hands":
        return -1  # Ensures "Hands" items appear at the very top

    # HEADGEAR
    if any(x in s for x in ["helmet", "face", "mask", "eyewear", "headgear"]) or any(x in i for x in ["helmet", "nvg", "balaclava", "hat", "goggles"]):
        return 0

    # SHOULDER LEFT
    if s == "shoulderl":
        return 1

    # SHOULDER RIGHT
    if s == "shoulderr":
        return 2

    # GLOVES
    if s == "gloves":
        return 3

    # BOOTS
    if s == "boots":
        return 4

    # BELT
    if s == "belt":
        return 5

    # VEST
    if s == "vest":
        return 6

    # BODY (Legs)
    if s == "body" or s == "legs":
        return 7

    # STORAGE (Back)
    if s == "back":
        return 8

    # EVERYTHING ELSE
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
        return (major, 0)

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
            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head><title>Error</title></head>
                <body>
                    <h1 style="color: red;">Error: No file uploaded.</h1>
                    <p>Please select a JSON file.</p>
                    <a href="/">Go back</a>
                </body>
                </html>
            """)

        file = request.files["file"]
        if file.filename == "":
            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head><title>Error</title></head>
                <body>
                    <h1 style="color: red;">Error: No selected file.</h1>
                    <p>Please choose a valid JSON file.</p>
                    <a href="/">Go back</a>
                </body>
                </html>
            """)

        try:
            if file.read(1) == b"":  
                return render_template_string("""
                    <!DOCTYPE html>
                    <html lang="en">
                    <head><title>Error</title></head>
                    <body>
                        <h1 style="color: red;">Error: Empty file.</h1>
                        <p>Please upload a valid JSON file.</p>
                        <a href="/">Go back</a>
                    </body>
                    </html>
                """)
            file.seek(0)

            json_data = json.load(file)

            if "name" not in json_data:
                return render_template_string("""
                    <!DOCTYPE html>
                    <html lang="en">
                    <head><title>Error</title></head>
                    <body>
                        <h1 style="color: red;">Error: Missing 'name' field.</h1>
                        <p>Your JSON file must include a "name" field at the top.</p>
                        <p><strong>Example of a correct JSON file:</strong></p>
                        <pre>
{
    "name": "ExampleLoadout",
    "attachmentSlotItemSets": [
        {
            "slotName": "hands",
            "discreteItemSets": [
                { "itemType": "M4A1" }
            ]
        }
    ]
}
                        </pre>
                        <p>Please edit your file and try again.</p>
                        <a href="/">Go back</a>
                    </body>
                    </html>
                """)

            xml_output = convert_json_to_xml(json_data)

            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>JSON to XML Converter</title>
                    <style>
                        body { font-family: Arial, sans-serif; background-color: #f4f4f4; text-align: center; padding: 20px; }
                        h1 { color: #333; }
                        .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1); max-width: 600px; margin: auto; }
                        pre { background: #eee; padding: 10px; border-radius: 5px; text-align: left; overflow-x: auto; }
                        a, button { display: inline-block; background: #007BFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px; border: none; cursor: pointer; }
                        a:hover, button:hover { background: #0056b3; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>XML Preview</h1>
                        <pre>{{ xml_output }}</pre>
                        <a href="/download?xml={{ xml_output | urlencode }}">Download XML</a>
                        <br><br>
                        <a href="/">Upload another file</a>
                    </div>
                </body>
                </html>
            """, xml_output=xml_output)

        except json.JSONDecodeError:
            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head><title>Error</title></head>
                <body>
                    <h1 style="color: red;">Error: Invalid JSON format.</h1>
                    <p>Please check your file and try again.</p>
                    <a href="/">Go back</a>
                </body>
                </html>
            """)

        except Exception as e:
            return render_template_string(f"""
                <!DOCTYPE html>
                <html lang="en">
                <head><title>Error</title></head>
                <body>
                    <h1 style="color: red;">Error processing file.</h1>
                    <p>{str(e)}</p>
                    <a href="/">Go back</a>
                </body>
                </html>
            """)

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>JSON to XML Converter</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f4f4f4; text-align: center; padding: 20px; }
                h1 { color: #333; }
                .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1); max-width: 400px; margin: auto; }
                input[type="file"] { display: block; margin: 10px auto; }
                button { background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                button:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Upload JSON File</h1>
                <form method="post" enctype="multipart/form-data">
                    <input type="file" name="file">
                    <button type="submit">Convert to XML</button>
                </form>
            </div>
        </body>
        </html>
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
