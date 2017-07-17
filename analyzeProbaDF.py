__author__ = "Alexandre Bovet"


import numpy as np
import pandas as pd
from multiprocessing import Pool
from functools import partial
import time

def applyParallel(dfGrouped, func, ncpu):
    with Pool(ncpu) as p:
        ret_list = p.map(func, [group for name, group in dfGrouped])
    return pd.concat(ret_list)


# aggregating functions: used on tweets grouped by day
def get_num_tweets(group, parallel=True):
    """ returns the number of tweets in each camp in group """
    
    # if there is no tweets for this day
    if group.index.size == 0:
        if parallel:
            return pd.DataFrame()
        else:
            return pd.Series()
            
    else:
        data = {'n_pro_1': group.n_pro_1.sum(),
                'n_pro_0': group.n_pro_0.sum()}
        
        if parallel:
            #must return a datafram when parallel
            return pd.DataFrame(data=data, index=[group.index[0].date()])
            
        else:
            return pd.Series(data=data)
            

def get_pro_h_ratio(ggroup):
    """ returns the ratio of tweets pro 1 in ggroup"""
    return ggroup.n_pro_1.sum()/ggroup.n_pro_1.size
    

def get_num_users(group, r_threshold=0.5, parallel=True):
    """ returns the number of users pro 1 in group with a ratio of
        tweets pro of at least r_threshold
    """
    
    if group.index.size == 0:
        if parallel:
            return pd.DataFrame()
        else:
            return pd.Series()
                
    else:
        # group tweets per users
        g_users = group.groupby('user_id')
        # ratio of pro hillary tweets for each user
        pro_h_ratio = g_users.apply(get_pro_h_ratio)
       
        n_pro_1 = (pro_h_ratio > r_threshold).sum()
        n_pro_0 = (pro_h_ratio < 1-r_threshold).sum()
        n_null = pro_h_ratio.size - n_pro_1 - n_pro_0

        data = {'n_pro_1': n_pro_1, 
                'n_pro_0': n_pro_0,
                'null': n_null}
                    
        if parallel:
            return pd.DataFrame(data=data, index=[group.index[0].date()])
        else:
            return pd.Series(data=data)
            
from ds import DS

class analyzeProbaDF(DS):
    """ analyze classification probability dataframe
        returns number of tweets and users per day for each camp
    """
    
    def run(self):
        #==============================================================================
        # PARAMETERS
        #==============================================================================
        df_proba_filename = self.job['df_proba_filename']
        df_num_tweets_filename = self.job['df_num_tweets_filename']
        df_num_users_filename = self.job['df_num_users_filename']
        
        #==============================================================================
        # OPTIONAL PARAMETERS
        #==============================================================================
        propa_col_name = self.job.get('propa_col_name', 'p_1')
        ncpu = self.job.get('ncpu', 6)
        resampling_frequency = self.job.get('resampling_frequency', 'D') # day
        # threshold for the classifier probability
        threshold = self.job.get('threshold',0.5)
        # threshold for the ratio of classified tweets needed to classify a user
        r_threshold = self.job.get('r_threshold',0.5)
        
        if ncpu == 1:
            parallel=False
        else:
            parallel=True

        print('loading ' + df_proba_filename)
        df = pd.read_pickle(df_proba_filename)

        
        #% filter dataframe according to threshold
        df_filt = df.drop(df.loc[np.all([df[propa_col_name] <= threshold, df[propa_col_name] >= 1-threshold], axis=0)].index)
        df_filt['n_pro_1'] = df_filt[propa_col_name] > threshold
        df_filt['n_pro_0'] = df_filt[propa_col_name] < 1 - threshold
        
        # resample tweets per day
        resample = df_filt.set_index('datetime_EST').groupby(pd.TimeGrouper(resampling_frequency))
        
        print('threshold: ' + str(threshold))
        print('r_threshold: ' + str(r_threshold))
        
        # prepare funtions for parallel apply
        get_num_tweets_u = partial(get_num_tweets,
                                   parallel=parallel)
        
        get_num_users_u = partial(get_num_users, r_threshold=r_threshold,
                                  parallel=parallel)
        
        print('computing stats')
        t0 = time.time()
        
        if parallel:
            df_num_tweets = applyParallel(resample, get_num_tweets_u, ncpu)            
            df_num_users = applyParallel(resample, get_num_users_u, ncpu)
            
        else:
            df_num_tweets = resample.apply(get_num_tweets_u)
            df_num_users = resample.apply(get_num_users_u)

        #%% save dataframes            
        df_num_tweets.to_pickle(df_num_tweets_filename)    
        df_num_users.to_pickle(df_num_users_filename)
        
        print('finished')
        print(time.time() - t0)
        
        self.string_results = "\nNumber of tweets per day in each camp:\n"+\
                                df_num_tweets.to_string() + \
                                "\nNumber of users per day in each camp:\n"+\
                                df_num_users.to_string()
        
        print(self.string_results)
        
            
            