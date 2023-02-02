import pandas as pd
#import utm
import numpy as np
import rasterio
#from meteostat import Stations, Monthly, Point
from datetime import datetime
import random
#from geopy.distance import geodesic as GD
import json
from scipy.stats import norm
import requests
class CropModel:
    
    def __init__(self):
        
        # General variables and configuration
        self.CropLabelName = ['ri1','ri2','ri3','ri4', 'mp', 'cf', 'sc', 'op', 'rb']
        self.FieldLatitude = 'lats'
        self.FieldLongitude = 'lons'
        
        # Base yield variables
        self.BaseYieldFilePath = 'Data/'
        self.BaseYieldVarianceFactor = 0.025 # Percent to variance
        self.BaseYieldAdditionalFactor = 0.1 # percent to additional 
        
        # Disaster variables
        self.DisasterRiskMapFile = 'Data/risk_map.tif'
        self.DisasterType = ['drought', 'flood']
        self.DisasterFloodReductionFactor = [0.45, 0.65] # Leftover ratio
        self.DisasterDroughtReductionFactor = [0.68, 0.83] # Leftover ratio
        
        # Rain variables
        self.OptimalRainForRice = [1500,600]  # optimal value, stdev
        self.OptimalRainForMaize = [700,200]  # optimal value, stdev
        self.OptimalRainForCassava = [1100,200]  # optimal value, stdev
        self.OptimalRainForSugarcane = [1400,200]  # optimal value, stdev
        self.OptimalRainForOilpalm = [1800,400]  # optimal value, stdev
        self.OptimalRainForRubber = [1800,300]  # optimal value, stdev
        
        
        # Temperatire variables
        self.OptimalTemperatureForRice = [25, 6] # optimal value, stdev
        self.OptimalTemperatureForMaize = [28.5, 10] # optimal value, stdev
        self.OptimalTemperatureForCassava = [25.5, 10] # optimal value, stdev
        self.OptimalTemperatureForSugarcane = [29, 6] # optimal value, stdev
        self.OptimalTemperatureForOilpalm = [27, 8] # optimal value, stdev
        self.OptimalTemperatureForRubber = [27.5, 9] # optimal value, stdev
        
        
        self.OptimalRainReductionFactors = [self.OptimalRainForRice]*4 + [self.OptimalRainForMaize] + [self.OptimalRainForCassava] + \
                                           [self.OptimalRainForSugarcane] + [self.OptimalRainForOilpalm] + [self.OptimalRainForRubber]
        
        self.OptimalTemperatureFactors = [self.OptimalTemperatureForRice]*4 + [self.OptimalTemperatureForMaize] + [self.OptimalTemperatureForCassava] + \
                                         [self.OptimalTemperatureForSugarcane] + [self.OptimalTemperatureForOilpalm] + [self.OptimalTemperatureForRubber]

        
    def fetch_agent_data(self, token, offset, limit):
        
        r=requests.get(f"http://13.229.114.44:1198/api/v1/farmer/agents?offset={offset}&limit={limit}", \
                       headers={'accept':'application/json', \
                                'X-Session-Token': token})
        
        data = r.json()['data']
        
        df = pd.DataFrame.from_dict(data)
        
        return df
        
        
    
    def convert_response_data_to_dataframe_0(self, response):
    
        data = response['data']

        df = pd.DataFrame.from_dict(data)

        return df
    
    def get_baseyield_1(self, agent_data):
        
        # make latlon set
        coordinateList = [(agent_data[self.FieldLongitude][i], agent_data[self.FieldLatitude][i]) for i in range(len(agent_data))]
        
        # for each crop
        for cropName in self.CropLabelName:
            
            with rasterio.open(self.BaseYieldFilePath+'yield_' + cropName +'.tif') as src:
                
                # sampling yield value from baseyield raster
                agent_data['baseyld_'+cropName] = [x[0] for x in src.sample(coordinateList)]
        
        # which one is not in yield map -> give NoValue
        agent_data = agent_data.replace(-9999, np.nan)
        
        return agent_data
    
    def vary_baseyield_2(self, agent_data):
        
        # Make N length of leftover yield
        randomFactorList = [random.uniform(1.0-self.BaseYieldVarianceFactor, 1.0+self.BaseYieldVarianceFactor) for i in range(len(agent_data))]
        
        for cropName in self.CropLabelName:
            
            # Calculate leftover yield for every crop
            agent_data['varyld_'+cropName] = agent_data['baseyld_'+cropName] * randomFactorList * (1.0+self.BaseYieldAdditionalFactor)
        
        return agent_data
    
    def shock_temp_3(self, agent_data, temp_range):
        
        ReductionFactorForTemp = 5 #5
        
        # sampling a temperature value in minmax range
        temperatureFromRandom = random.uniform(temp_range[0], temp_range[1])
        
        # Generate Shock factor from temp
        shockFactorsListForEachCrop = []
        
        for cropName, temperatureFactorAtCrop in zip(self.CropLabelName, self.OptimalTemperatureFactors):
            
            shockFactorsListForEachCrop.append(self.get_shock_factor(temperatureFromRandom, temperatureFactorAtCrop[0], temperatureFactorAtCrop[1], ReductionFactorForTemp))
        
        # for each crop
        for i, cropName in enumerate(self.CropLabelName):
            
            agent_data['tmpshk_'+cropName] = agent_data['varyld_'+cropName] * shockFactorsListForEachCrop[i]
        
        return agent_data
    
    def shock_rain_4(self, agent_data, rain_range):
        
        ReductionFactorForRain = 20 #20
        
        # sampling a temperature value in minmax range
        rainFromRandom = random.uniform(rain_range[0], rain_range[1])
        
        # Generate Shock factor from temp
        shockFactorsListForEachCrop = []
        
        for cropName, rainFactorAtCrop in zip(self.CropLabelName, self.OptimalRainReductionFactors):
            
            shockFactorsListForEachCrop.append(self.get_shock_factor(rainFromRandom, rainFactorAtCrop[0], rainFactorAtCrop[1], ReductionFactorForRain))
        
        # for each crop
        for i, cropName in enumerate(self.CropLabelName):
            
            agent_data['ranshk_'+cropName] = agent_data['tmpshk_'+cropName] * shockFactorsListForEachCrop[i]
        
        return agent_data
    
    def shock_disaster_5(self, agent_data):
        
        coordinateList = [(agent_data[self.FieldLongitude][i], agent_data[self.FieldLatitude][i]) for i in range(len(agent_data))]
        
        with rasterio.open(self.DisasterRiskMapFile) as src:
                
            # sampling yield value from baseyield raster
            sampleRiskValues = [x[0] for x in src.sample(coordinateList)]
        
        is_disaster = [1 if random.random() < sampleRiskValues[i] else 0 for i in range(len(sampleRiskValues))]

        disaster_type = random.choice(self.DisasterType)
        
        if disaster_type == 'flood':
            max_severe_list = [random.uniform(self.DisasterFloodReductionFactor[0], self.DisasterFloodReductionFactor[1]) for i in range(len(is_disaster))]
        else:
            max_severe_list = [random.uniform(self.DisasterDroughtReductionFactor[0], self.DisasterDroughtReductionFactor[1]) for i in range(len(is_disaster))]
        
        severity_percent = [random.random() if is_disaster[i] else 0 for i in range(len(sampleRiskValues))]
        
        left_over_yield_ratio = [1-((1-max_severe_list[i])* severity_percent[i]) if is_disaster[i] else 1. for i in range(len(sampleRiskValues))]

        # for each crop
        for i, cropName in enumerate(self.CropLabelName):
            
            agent_data['dis_'+cropName] = agent_data['ranshk_'+cropName] * left_over_yield_ratio
            
        agent_data['dis_severity'] = severity_percent
        
        return agent_data
    
    def clean_agent_data(self, agent_data, is_disaster):
        
        if not is_disaster:
            
            output_columns = ['ids'] + ['ranshk_'+cropName for cropName in self.CropLabelName]
            clean_columns = ['ids'] + [cropName for cropName in self.CropLabelName]
        else:
            output_columns = ['ids'] + ['dis_'+cropName for cropName in self.CropLabelName] +\
                             ['dis_severity']
            clean_columns = ['ids'] + [cropName for cropName in self.CropLabelName] +\
                             ['severity']
        
        output_dataframe = agent_data[output_columns]
        
        output_dataframe.columns = clean_columns
        
        
        return output_dataframe
            
        
    def convert_result_to_response_6(self, data):
        
        result = {}
        
        for col in data.columns:
            
            result[col] = data[col].values.tolist()
            
        return result
    
    # A function to calculate leftover yield variance from optimal enviroment factors of each crop
    # x = current env (tmp or rain), mu = optimal env, sigma = stdev env, reduction_factor= multiplication number for preventing over reduce yield
    def get_shock_factor(self, x, mu, sigma, reduction_factor):
        
        return (1-norm.cdf(mu+abs(mu-x), mu, sigma*reduction_factor))*2