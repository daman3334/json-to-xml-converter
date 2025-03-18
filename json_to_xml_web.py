from flask import Flask, request, render_template_string, send_file
import json
import xml.etree.ElementTree as ET
import io

app = Flask(__name__)

def convert_json_to_xml(json_data):
    root = ET.Element("type", name=json_data["name"])
    
    # Process attachmentSlotItemSets
    for slot_data in json_data.get("attachmentSlotItemSets", []):
        mapped_slot = slot_data["slotName"]
        for item_set in slot_data["discreteItemSets"]:
            item_name = item_set["itemType"]
            block = ET.SubElement(root, "attachments", chance="1")
            ET.SubElement(block, "item", name=item_name, chance="1.00")

    return ET.tostring(root, encoding="unicode", method="xml")

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
            
            # Show preview
            return render_template_string("""
                <h2>XML Preview</h2>
                <pre>{{ xml_output }}</pre>
                <a href="/download?xml={{ xml_output | urlencode }}">Download XML</a>
                <br><br>
                <a href="/">Upload another file</a>
            """, xml_output=xml_output)
        except Exception as e:
            return f"Error processing file: {str(e)}"

    return '''
        <h1>Upload JSON File</h1>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="Convert to XML">
        </form>
    '''

@app.route("/download")
def download_file():
    xml_content = request.args.get("xml", "")
    
    if not xml_content:
        return "No XML content to download"
    
    xml_file = io.BytesIO(xml_content.encode("utf-8"))
    xml_file.seek(0)
    
    return send_file(xml_file, as_attachment=True, download_name="output.xml", mimetype="text/xml")

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Use Render's assigned port
    app.run(host="0.0.0.0", port=port)
