import torch
import os
import torch.nn.functional as F
import numpy as np
import math
import ignite
import matplotlib.pyplot as plt
from torch import TracingState, nn, tensor, tensor_split
from torch.utils.data import DataLoader, TensorDataset
from torchvision import datasets
from torchvision.transforms import ToTensor, Lambda

from ignite.engine import *
from ignite.handlers import *
from ignite.metrics import *
from ignite.utils import *
from ignite.contrib.metrics.regression import *
from ignite.contrib.metrics import *


docCount = 2;

#> hyperparamètres
learning_rate = 1e-3
batch_size = 64
epochs = 1


device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using {device} device")

#> chargement du de données
code = {1247:0 , 1302:1 , 1326:2 , 170:3 , 187:4 , 237:5 , 2473:6 , 29193:7 , 29662:8 , 29663:9 , 30324:10 , 30325:11 , 32248:12 , 32249:13 , 40357:14 , 40358:15, 480:16 , 58:17 , 7578:18, 86:19 , 0:20 , 1:21 , 2:22}

path = "data\CTce_ThAb_b33x33_n1000_8bit"
directory = os.fsencode(path)

patients = []
groups = []

cpt = 0
for file in os.listdir(directory):
    filename = os.fsdecode(file)
    if filename.endswith(".csv"):
        print("Reading ", filename)

        labels = np.loadtxt(path + "\\" + filename, delimiter=",", usecols=0)
        #labels = np.vectorize(code.get)(labels)

        labels_set = np.unique(labels)

        dic = {}
        for i in range(len(labels_set)):
            dic[labels_set[i]] = i

        labels = np.vectorize(dic.get)(labels)

        labels_tensor = torch.from_numpy(labels)
        labels_tensor = labels_tensor.type(torch.FloatTensor)
        labels_tensor = labels_tensor.to(device)

        images_1D = np.loadtxt(path + "\\" + filename, delimiter=",", usecols=np.arange(1,1090))
        images_2D = images_1D.reshape(images_1D.shape[0], 1, 33, 33)
        images_tensor = torch.from_numpy(images_2D)
        images_tensor = images_tensor.type(torch.FloatTensor)
        images_tensor = images_tensor.to(device)

        patients.append(TensorDataset(images_tensor, labels_tensor))

        cpt += 1
        if(cpt == docCount):
            break

#patients = torch.utils.data.ConcatDataset(patients) // à ne pas considérer
#train_sampler, valid_sampler = torch.utils.data.random_split((patients), [math.floor(len(patients)*0.8), len(patients)-math.floor(len(patients)*0.8)])

#for i in range(4):
#    groups.append( torch.utils.data.ConcatDataset((patients[5*i], patients[5*i+1], patients[5*i+2], patients[5*i+3], patients[5*i+4])) )



#> définition du réseau
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        # 1 x 33 x 33
        self.conv1 = nn.Conv2d(1, 20, 18, stride=1, padding=0, dilation=1)
        self.pool = nn.MaxPool2d(2)
        self.conv2 = nn.Conv2d(20, 40, 4, stride=1, padding=0, dilation=1)
        self.fc1 = nn.Linear(160, 80)
        self.fc2 = nn.Linear(80, 30)
        self.fc3 = nn.Linear(30, 23)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1) # flatten all dimensions except batch
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

model = Net()
model = Net().to(device)
model.to(torch.float)

#> boucle d'apprentissage
def train_loop(dataloader, model, loss_fn, optimizer):
    size = len(dataloader.dataset)
    correct, train_loss = 0, 0
    for batch, (X, y) in enumerate(dataloader):
        # Compute prediction and loss
        pred = model(X)
        loss = loss_fn(pred, y.long())
        train_loss += loss_fn(pred, y.long()).item()

        # Backpropagation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        correct += (pred.argmax(1) == y).type(torch.float).sum().item()

    train_loss /= len(dataloader)
    correct /= size
    print("TRAIN LOOP")
    print("    loss: ", train_loss)
    print("    accuracy: ", 100*correct)

#> boucle de validation
def valid_loop(dataloader, model, loss_fn):
    y_pred = []
    y_true = []
    size = len(dataloader.dataset)
    num_batches = len(dataloader)
    test_loss, correct = 0, 0

    with torch.no_grad():
        for X, y in dataloader:
            pred = model(X)
            y_pred.extend(pred)
            y_true.extend(y)

            test_loss += loss_fn(pred, y.long()).item()
            correct += (pred.argmax(1) == y).type(torch.float).sum().item()

    test_loss /= num_batches
    correct /= size
    print("TEST LOOP")
    print("    loss: ", test_loss)
    print("    accuracy: ", 100*correct)
    print("")
    return y_pred, y_true

#> fonction de perte et algorythme d'optimisation
loss_fn = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)

def eval_step(engine, batch):
    return batch

default_evaluator = Engine(eval_step)

#> execution de l'apprentissage et des tests
for k in range(1): # itération sur 4 plis
    print(f"Fold {k+1}\n-------------------------------\n-------------------------------")
    #train_sampler = torch.utils.data.ConcatDataset(( groups[(k+1)%4], groups[(k+2)%4], groups[(k+3)%4] ))
    #valid_sampler = groups[k]
    train_sampler = patients[0]
    valid_sampler = patients[1]
    train_dataloader = DataLoader(train_sampler, batch_size=batch_size, shuffle=True)
    valid_dataloader = DataLoader(valid_sampler, batch_size=batch_size, shuffle=True)

    y_pred_all = []
    y_true_all = []
    for t in range(epochs): # itération sur les epochs
        print(f"Epoch {t+1}\n-------------------------------")
        train_loop(train_dataloader, model, loss_fn, optimizer)
        y_pred, y_true = valid_loop(valid_dataloader, model, loss_fn)
        y_pred_all.extend(y_pred)
        y_true_all.extend(y_true)
    print("Done!")
    metric = ignite.metrics.confusion_matrix.ConfusionMatrix(num_classes=23)
    metric.attach(default_evaluator, 'cm')
    #y_pred_tensor = torch.FloatTensor(y_pred_all)
    #y_true_tensor = torch.FloatTensor(y_true_all)
    y_pred = torch.stack(y_pred_all)
    print(y_pred)
    a = input("yolo")
    y_true = torch.stack(y_true_all)
    print(y_true)
    state = default_evaluator.run([[y_pred, y_true]])
    print(state.metrics['cm'])