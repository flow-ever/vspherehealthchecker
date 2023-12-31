import os

data_dir= os.path.join(os.getcwd(),'data')
log_dir=os.path.join(data_dir,'log')

if not os.path.exists(log_dir):
    # os.mkdir(log_dir)
    os.makedirs(log_dir)