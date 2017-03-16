# coding=utf-8

import pygame
import random
from pygame.locals import *
import numpy as np
from collections import deque
import tensorflow as tf  # http://blog.topspeedsnail.com/archives/10116
import cv2               # http://blog.topspeedsnail.com/archives/4755
import os 
import sys
 
BLACK     = (0  ,0  ,0  )
WHITE     = (255,255,255)
 
SCREEN_SIZE = [320,400]
BAR_SIZE = [50, 5]
BALL_SIZE = [15, 15]
 
# 神经网络的输出
MOVE_STAY = [1, 0, 0]
MOVE_LEFT = [0, 1, 0]
MOVE_RIGHT = [0, 0, 1]
 
class Game(object):
    def __init__(self):
        pygame.init()
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption('Simple Game')
 
        self.ball_pos_x = SCREEN_SIZE[0]//2 - BALL_SIZE[0]/2
        self.ball_pos_y = SCREEN_SIZE[1]//2 - BALL_SIZE[1]/2
 
        self.ball_dir_x = -1 # -1 = left 1 = right  
        self.ball_dir_y = -1 # -1 = up   1 = down
        self.ball_pos = pygame.Rect(self.ball_pos_x, self.ball_pos_y, BALL_SIZE[0], BALL_SIZE[1])
 
        self.bar_pos_x = SCREEN_SIZE[0]//2-BAR_SIZE[0]//2
        self.bar_pos = pygame.Rect(self.bar_pos_x, SCREEN_SIZE[1]-BAR_SIZE[1], BAR_SIZE[0], BAR_SIZE[1])
 
    # action是MOVE_STAY、MOVE_LEFT、MOVE_RIGHT
    # ai控制棒子左右移动；返回游戏界面像素数和对应的奖励。(像素->奖励->强化棒子往奖励高的方向移动)
    def step(self, action):
 
        if action == MOVE_LEFT:
            self.bar_pos_x = self.bar_pos_x - 2
        elif action == MOVE_RIGHT:
            self.bar_pos_x = self.bar_pos_x + 2
        else:
            pass
        if self.bar_pos_x < 0:
            self.bar_pos_x = 0
        if self.bar_pos_x > SCREEN_SIZE[0] - BAR_SIZE[0]:
            self.bar_pos_x = SCREEN_SIZE[0] - BAR_SIZE[0]
            
        self.screen.fill(BLACK)
        self.bar_pos.left = self.bar_pos_x
        pygame.draw.rect(self.screen, WHITE, self.bar_pos)
 
        self.ball_pos.left += self.ball_dir_x * 2
        self.ball_pos.bottom += self.ball_dir_y * 3
        pygame.draw.rect(self.screen, WHITE, self.ball_pos)
 
        if self.ball_pos.top <= 0 or self.ball_pos.bottom >= (SCREEN_SIZE[1] - BAR_SIZE[1]+1):
            self.ball_dir_y = self.ball_dir_y * -1
        if self.ball_pos.left <= 0 or self.ball_pos.right >= (SCREEN_SIZE[0]):
            self.ball_dir_x = self.ball_dir_x * -1
 
        reward = 0
        if self.bar_pos.top <= self.ball_pos.bottom and (self.bar_pos.left < self.ball_pos.right and self.bar_pos.right > self.ball_pos.left):
            reward = 1    # 击中奖励
        elif self.bar_pos.top <= self.ball_pos.bottom and (self.bar_pos.left > self.ball_pos.right or self.bar_pos.right < self.ball_pos.left):
            reward = -1   # 没击中惩罚
 
        # 获得游戏界面像素
        screen_image = pygame.surfarray.array3d(pygame.display.get_surface())
        pygame.display.update()
        # 返回游戏界面像素和对应的奖励
        return reward, screen_image
 
# learning_rate
LEARNING_RATE = 0.99
# 更新梯度
INITIAL_EPSILON = 1.0
FINAL_EPSILON = 0.05
# 测试观测次数
EXPLORE = 10000 
OBSERVE = 1000
# 存储过往经验大小
REPLAY_MEMORY = 10000
 
BATCH = 100

curr_dir = os.path.dirname(__file__)
data_dir = os.path.join(curr_dir, "data")
model_dir = os.path.join(curr_dir, "game_model")
if not os.path.exists(model_dir):
    os.mkdir(model_dir)

output = 3  # 输出层神经元数。代表3种操作-MOVE_STAY:[1, 0, 0]  MOVE_LEFT:[0, 1, 0]  MOVE_RIGHT:[0, 0, 1]
input_image = tf.placeholder("float", [None, 80, 100, 4])  # 游戏像素
action = tf.placeholder("float", [None, output])     # 操作
 
# 定义CNN-卷积神经网络 参考:http://blog.topspeedsnail.com/archives/10451
def convolutional_neural_network(input_image):
    weights = {'w_conv1':tf.Variable(tf.zeros([8, 8, 4, 32])),
               'w_conv2':tf.Variable(tf.zeros([4, 4, 32, 64])),
               'w_conv3':tf.Variable(tf.zeros([3, 3, 64, 64])),
               'w_fc4':tf.Variable(tf.zeros([3456, 784])),
               'w_out':tf.Variable(tf.zeros([784, output]))}
 
    biases = {'b_conv1':tf.Variable(tf.zeros([32])),
              'b_conv2':tf.Variable(tf.zeros([64])),
              'b_conv3':tf.Variable(tf.zeros([64])),
              'b_fc4':tf.Variable(tf.zeros([784])),
              'b_out':tf.Variable(tf.zeros([output]))}
    # input_image : (?, 80, 100, 4)
    conv1 = tf.nn.relu(tf.nn.conv2d(input_image, weights['w_conv1'], strides = [1, 4, 4, 1], padding = "VALID") + biases['b_conv1'])
    # conv1 : （？， 19， 24， 32）
    conv2 = tf.nn.relu(tf.nn.conv2d(conv1, weights['w_conv2'], strides = [1, 2, 2, 1], padding = "VALID") + biases['b_conv2'])
    # conv2 :  (?, 8, 11, 64)
    conv3 = tf.nn.relu(tf.nn.conv2d(conv2, weights['w_conv3'], strides = [1, 1, 1, 1], padding = "VALID") + biases['b_conv3'])
    # conv3 :  (?, 6, 9, 64)
    conv3_flat = tf.reshape(conv3, [-1, 3456])
    # conv3_flat : (?, 3456)
    fc4 = tf.nn.relu(tf.matmul(conv3_flat, weights['w_fc4']) + biases['b_fc4'])
    # fc4 : (?, 784)
    output_layer = tf.matmul(fc4, weights['w_out']) + biases['b_out']
    # output_layer : (?, 3)
    return output_layer
 
# 深度强化学习入门: https://www.nervanasys.com/demystifying-deep-reinforcement-learning/
# 训练神经网络
def train_neural_network(input_image):
    predict_action = convolutional_neural_network(input_image)  # (?, 3)

    argmax = tf.placeholder("float", [None, output])
    gt = tf.placeholder("float", [None])
 
    action = tf.reduce_sum(tf.multiply(predict_action, argmax), reduction_indices = 1)
    cost = tf.reduce_mean(tf.square(action - gt))
 

    # 定义学习速率和优化方法
    global_step = tf.Variable(0, trainable=False)
    learning_rate = tf.train.exponential_decay(1e-3, global_step, 1000, 0.96, staircase=True)

#    optimizer = tf.train.AdamOptimizer(1e-6).minimize(cost)

    optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost, global_step=global_step)

    game = Game()
    D = deque()
 
    _, image = game.step(MOVE_STAY)
    # 转换为灰度值
    image = cv2.cvtColor(cv2.resize(image, (100, 80)), cv2.COLOR_BGR2GRAY)
    # 转换为二值
    ret, image = cv2.threshold(image, 1, 255, cv2.THRESH_BINARY)    # image shape: (80, 100)
    input_image_data = np.stack((image, image, image, image), axis = 2) # shape: (80, 100, 4)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
                
        saver_prefix = os.path.join(model_dir, "model.ckpt")        
        ckpt = tf.train.get_checkpoint_state(model_dir)
        saver = tf.train.Saver(max_to_keep=1)

        # n = 0
        # epsilon = INITIAL_EPSILON

        if ckpt and ckpt.model_checkpoint_path:
            print("restore model ...")
            saver.restore(sess, ckpt.model_checkpoint_path)

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(coord=coord, sess=sess)         
        # n = 0   
        while not coord.should_stop():
        # while True:
            
            # 获得预测的步骤
            action_t = predict_action.eval(feed_dict = {input_image : [input_image_data]})[0]
            argmax_t = np.zeros([output], dtype=np.int)
            # if(random.random() <= INITIAL_EPSILON):
            # 随机动一下
            maxIndex = random.randrange(output)
            # else:
                # maxIndex = np.argmax(action_t)
            argmax_t[maxIndex] = 1


            # if epsilon > FINAL_EPSILON:
            #     epsilon -= (INITIAL_EPSILON - FINAL_EPSILON) / EXPLORE
 
            # 游戏按预测的下一步
            for event in pygame.event.get():  # macOS需要事件循环，否则白屏
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()                    
            reward, image = game.step(list(argmax_t))           
 
            # 获得游戏截图
            image = cv2.cvtColor(cv2.resize(image, (100, 80)), cv2.COLOR_BGR2GRAY)
            ret, image = cv2.threshold(image, 1, 255, cv2.THRESH_BINARY)
            image = np.reshape(image, (80, 100, 1))
            input_image_data1 = np.append(image, input_image_data[:, :, 0:3], axis = 2)
 
            # 添加到list中
            D.append((input_image_data, argmax_t, reward, input_image_data1))
 
            # 如果list太长，删除最早的
            if len(D) > REPLAY_MEMORY:
                D.popleft()
 
            # if n > OBSERVE:
            if len(D) >= BATCH:
                # 从列表中抓出一批照片
                minibatch = random.sample(D, BATCH)
                input_image_data_batch = [d[0] for d in minibatch]
                argmax_batch = [d[1] for d in minibatch]
                reward_batch = [d[2] for d in minibatch]
                input_image_data1_batch = [d[3] for d in minibatch]
 
                # 对结果进行评价
                gt_batch = []
                
                # 获得预测的步骤
                out_batch = predict_action.eval(feed_dict = {input_image : input_image_data1_batch})

                for i in range(0, len(minibatch)):
                    gt_batch.append(reward_batch[i] + 0.99 * np.max(out_batch[i]))
 
                # optimizer.run(feed_dict = {gt : gt_batch, argmax : argmax_batch, input_image : input_image_data_batch})
                # 将评价的结果重新输入到系统进行学习
                _, _step=sess.run([optimizer,global_step],feed_dict = {gt : gt_batch, argmax : argmax_batch, input_image : input_image_data_batch})
                if _step % 10 == 0:                
                   saver.save(sess, saver_prefix, global_step=_step)  # 保存模型
                   print(_step, " " ,"action:", maxIndex, " " ,"reward:", reward)
           
            input_image_data = input_image_data1
            # n = n+1           
            # print(n, " " ,"action:", maxIndex, " " ,"reward:", reward)

        # coord.request_stop()
        # coord.join(threads)

train_neural_network(input_image)