import copy
import time
import logging
import numpy as np
import torch
import torchmetrics

logger = logging.getLogger(__name__)

CLIENT_ACC = 'train_acc'
CLIENT_LOSS = 'train_loss'

class BaseClient(object):
    '''The base client class in federated learning

    '''
    def __init__(self, client_id, config, local_trainset, local_testset, device, train_datasize):
        self.client_id = client_id
        self.config = config.client

        self.local_trainset = local_trainset
        self.train_datasize = train_datasize
        self.local_testset = local_testset

        self.device = device

        # self.compressed_model = None
        self.local_model = None

        self.train_time = 0

        self.train_records = {CLIENT_ACC: [], CLIENT_LOSS: []}

    def download(self, model):
        '''  Download the global model from the server, the global model might be compressed
        '''
        # if self.compressed_model is not None:
        #     self.compressed_model.load_state_dict(model.state_dict())
        # else:
        #     self.compressed_model = copy.deepcopy(model)
        if self.local_model is not None:
            self.local_model.load_state_dict(model.state_dict())
        else:
            self.local_model = copy.deepcopy(model)

    # def decompress(self):
    #     ''' The function is set to be overwritten if there is a compress algorithm applied.
    #     Here, we set the default setting, transferring the model without any compress and decompress
    #     '''
    #     self.local_model = self.compressed_model
    #     # delete the cache of the downloaded global model
    #     # self.compressed_model = None

    def train_preparation(self):
        '''The function prepares the basic tools or operations in the local training process
        '''

        # loss function 
        loss_fn = self.load_loss_function()
        # optimizer
        optimizer = self.load_optimizer()
        # set model to device
        self.local_model.train()
        self.local_model.to(self.device)
        
        return loss_fn, optimizer

    def load_loss_function(self):
        if self.config.loss_fn == 'cross_entropy':
            return torch.nn.CrossEntropyLoss()
        elif self.config.loss_fn == 'mse':
            return torch.nn.MSELoss()
        else: 
            # defualt is cross entropy
            return torch.nn.CrossEntropyLoss().to(self.device)

    def load_optimizer(self):
        
        if self.config.optimizer.type == 'Adam':
            optimizer = torch.optim.Adam(self.local_model.parameters(), lr=self.config.optimizer.lr)
        elif self.config.optimizer.type == 'SGD':
            optimizer = torch.optim.SGD(self.local_model.parameters(), lr=self.config.optimizer.lr, momentum=self.config.optimizer.momentum, weight_decay=self.config.optimizer.weight_decay)
        else:
            # defualt is Adam
            optimizer = torch.optim.Adam(self.local_model.parameters(), lr=self.config.optimizer.lr)
        return optimizer


    def train(self):
        ''' Local training.

        Key variables:
        local_model: the model in the client and prepared to train with the local data
        local_trianset: the local data set stored in the client(local device)
        local_epochs: the iterations of the local training
        optimizer: the local optimizer for the local training

        '''    
        start_time = time.time()
        loss_fn, optimizer = self.train_preparation()
        train_accuracy = torchmetrics.Accuracy().to(self.device)

        for e in range(self.config.local_epoch):
            batch_loss = []
            train_accuracy.reset()
            for imgs, labels in self.local_trainset:
                imgs, labels = imgs.to(self.device), labels.to(self.device)
                optimizer.zero_grad()
                outputs = self.local_model(imgs)

                # Loss and model parameters update
                loss = loss_fn(outputs, labels)
                loss.backward()
                optimizer.step()
                batch_loss.append(loss.item())

                # Accuracy
                # pred = outputs.data.max(1)[1]
                # correct += pred.eq(labels.data.view_as(pred)).sum().item()
                _ = train_accuracy(outputs, labels)

            current_epoch_loss = np.mean(batch_loss)
            # current_epoch_acc = float(correct)/float(self.train_datasize)
            current_epoch_acc = train_accuracy.compute().item()

            self.train_records[CLIENT_LOSS].append(current_epoch_loss)
            self.train_records[CLIENT_ACC].append(current_epoch_acc)
            logger.debug('Client: {}, local epoch: {}, loss: {:.4f}, acc: {:.4f}'.format(self.client_id, e, current_epoch_loss, current_epoch_acc))
        self.train_time = time.time() - start_time
        logger.debug('Client: {}, training {:.4f}s'.format(self.client_id, self.train_time))


    # def compress(self):
    #     '''The description is shown in the function decompress
    #     '''
    #     self.compressed_model = self.local_model
    #     # self.local_model = None

    def upload(self):
        '''Upload the local models(compressed, if it is) to the server
        '''
        return self.local_model

    def step(self, global_model, is_train=True):
        
        self.download(global_model)       
        if is_train:
            # self.train_preparation()
            self.train() 
             
        return self.upload()







    



