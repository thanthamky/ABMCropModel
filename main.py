from flask import Flask, request #เพิ่ม request
from ast import literal_eval
from datetime import datetime

from CropModel import CropModel

token = 'LzOjl197e3OVFvGI'
offset_agent = 0
limit_agent = 675

raw_data = None

app = Flask(__name__)

model = CropModel()


@app.route('/')
def main():

    raw_data = model.fetch_agent_datffseta(token, offset_agent, limit_agent)

    #if raw_data is None:
      #  raw_data = model.fetch_agent_data(token, offset_agent, limit_agent)

    rain = request.args.get('rain')
    #rain = rain.strip(')(').split(', ')
    rain = eval(rain)

    temp = request.args.get('temp')
    #temp = temp.strip(')(').split(', ')
    temp = eval(temp)

    disaster = request.args.get('diss')
    disaster = eval(disaster)

    print(rain)
    print(temp)

    disaster = request.args.get('diss')

    data = model.get_baseyield_1(raw_data)
    data = model.vary_baseyield_2(data)
    data = model.shock_temp_3(data, [temp[0], temp[1]])
    data = model.shock_rain_4(data, [rain[0], rain[1]])

    if disaster:

        data = model.shock_disaster_5(data)
        data = model.clean_agent_data(data, is_disaster=True)

    else:
        data = model.clean_agent_data(data, is_disaster=False)

    result = model.convert_result_to_response_6(data)
    #print(result)

    return result


raw_data = model.fetch_agent_data(token, offset_agent, limit_agent)

app.run(host='0.0.0.0', debug=True)