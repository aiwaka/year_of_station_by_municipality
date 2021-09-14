from flask import Flask, render_template
import re

app = Flask(__name__, template_folder=".")


@app.route("/")
def index():
    try:
        with open("log.log") as f:
            log_list = [
                re.sub(r"\[.*?\] ", "", line.strip(), count=1) for line in f.readlines()
            ]
        if "summary:" in log_list:
            sum_index = log_list.index("summary:")
            summary = log_list[sum_index + 1 :]  # noqa: E203
            log_list = log_list[:sum_index]
        else:
            summary = []
        data_num = len([line for line in log_list if "got" in line])
    except Exception as e:
        print(e)
        log_list = []
        summary = []
        data_num = 0
    return render_template(
        "test.html", log_list=log_list, summary=summary, data_num=data_num
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=70)
