"""The three baselines every later model has to beat.

persistence  flow on the target day = flow on the day the forecast is issued
seasonal     flow on the target day = the usual flow for that day of the year
gbm          gradient boosting, one model per catchment and per lead time
"""
