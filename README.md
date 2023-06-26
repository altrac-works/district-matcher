# US Legislative Districts Matcher

It does two things:

* Download shapefiles from the Census TIGER dataset, convert them into GeoJSON, annotate them with OCDIDs
* Match coordinates against those shapefiles intelligently and returns OCDIDs (and other district properties) for relevant districts

## TODO

* OCDID quality control
* Benchmarking and optimization
* API service
* AWS Lambda deployment option

## Dependencies

* shapely compiled against libgeos
