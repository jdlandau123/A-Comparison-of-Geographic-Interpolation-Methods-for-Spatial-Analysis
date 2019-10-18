
# coding: utf-8

# In[11]:


import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd 
import shapely.geometry


# In[2]:


# add data
supermarkets_csv = pd.read_csv( # path to  supermarkets.csv )
land_use = gpd.read_file( # path to land_use.shp )
demographics_csv = pd.read_csv ( # path to demographics.csv )
census_tracts = gpd.read_file( # path to orange_county_census_tracts.shp )
market_areas = gpd.read_file( # path to market_areas.shp )


# In[3]:


# clean up demographics table columns
demographics_df = pd.read_csv(demographics_csv)

demographics_df.rename(columns={
	"B01003_001E":"TotalPop",
	"B11016_001E":"TotalHH",
	"B19025_001E":"AggHHIncome",
	"tract":"TRACT"}, inplace=True)

demographics_df.drop(labels=["B01003_001M", "B11016_001M", "B19025_001M", "state", "county"], 
	axis=1, inplace=True)


# In[4]:


# join demographics data to census tracts
demographics_df["TRACT"] = demographics_df["TRACT"].astype(int)
census_tracts["TRACT"] = census_tracts["TRACT"].astype(int)
tracts_final = census_tracts.merge(demographics_df, on="TRACT")


# In[5]:


# project shapefiles to same coordinate reference system
crs = {'init': 'epsg:3087'} #NAD83(HARN) Florida GDL Albers

land_use_wgs = land_use.to_crs(crs)
census_tracts_wgs = tracts_final.to_crs(crs)
market_areas_wgs = market_areas.to_crs(crs)


# In[6]:


'''  CHANGE IN WORKFLOW - THIS STEP WAS NO LONGER NECESSARY
# create supermarket points
supermarket_pts = gpd.GeoDataFrame(supermarkets_csv, 
	geometry=gpd.points_from_xy(supermarkets_csv.longitude, supermarkets_csv.latitude),
	crs=crs)
'''


# In[7]:


# compute area of each census tract and market area
census_tracts_wgs["area(m)_tracts"] = census_tracts_wgs["geometry"].area
market_areas_wgs["area(m)_markets"] = market_areas_wgs["geometry"].area


# In[8]:


# AREA WEIGHTED INTERPOLATION

# intersect census tracts with market areas 
cross = gpd.overlay(census_tracts_wgs, market_areas_wgs, how='union')

# calculate demographic stats
cross["area(m)_cross"] = cross["geometry"].area
cross["perc_land_area_cross"] = cross["area(m)_cross"] / cross["area(m)_tracts"]
cross["pop_cross"] = cross["TotalPop"] * cross["perc_land_area_cross"]
cross["hh_cross"] = cross["TotalHH"] * cross["perc_land_area_cross"]
cross["income_cross"] = cross["AggHHIncome"] * cross["perc_land_area_cross"]

# re-group by census tract
cross_dissolve = cross.dissolve(by='TRACT', aggfunc='sum')

# calculate average household income
cross_dissolve["avg_hh_income_aw"] = cross_dissolve["income_cross"] / cross_dissolve["hh_cross"]


# In[9]:


# ANCILLARY WEIGHTED INTERPOLATION

# calculate total area of residential land parcels in each census tract
anc_orange = land_use_wgs.loc[land_use_wgs["CNTYNAME"] == "ORANGE"]
residential = anc_orange.loc[anc_orange["DESCRIPT"] == "RESIDENTIAL"]

ancillary_tracts = gpd.overlay(residential, cross, how='union')
ancillary_tracts["area(m)_ancillary_tracts"] = ancillary_tracts['geometry'].area
ancillary_tracts_grouped = ancillary_tracts.dissolve(by='Tract_', aggfunc='sum')

# calculate residential land area in each polygon from cross
cross_dissolve.insert(0, 'id', range(0, 0 + len(cross_dissolve)))
ancillary_cross = gpd.overlay(residential, cross_dissolve, how='union')
ancillary_cross["area(m)_ancillary_cross"] = ancillary_cross['geometry'].area
ancillary_cross_grouped = ancillary_cross.dissolve(by='id', aggfunc='sum')

# merge area weighted and ancillary cross data
ancillary_final = gpd.overlay(ancillary_cross_grouped, ancillary_tracts_grouped, how='union')

# calculate demographic stats
ancillary_final["perc_land_area_anc"] = ancillary_final["area(m)_tracts_1"] / ancillary_final["area(m)_ancillary_tracts"]
ancillary_final["pop_anc"] = ancillary_final["TotalPop_1"] * ancillary_final["perc_land_area_anc"]
ancillary_final["hh_anc"] = ancillary_final["TotalHH_1"] * ancillary_final["perc_land_area_anc"]
ancillary_final["income_anc"] = ancillary_final["AggHHIncome_1"] * ancillary_final["perc_land_area_anc"]

# calculate average household income
ancillary_final["avg_hh_income_anc"] = ancillary_final["income_anc"] / ancillary_final["hh_anc"]


# In[ ]:


# write results to a shapefile
cross_dissolve.to_file("area_weighted_results.shp")
ancillary_final.to_file("ancillary_weighted_results.shp")

