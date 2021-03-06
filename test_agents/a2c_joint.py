import gym
import tensorflow as tf
import numpy as np


""""""""""
Actor-Critic [Monte-Carlo prediction and TD(0) for Advantage estimation]
with Joint Neural Network

"""""""""


class Buffer():
    def __init__(self):
        self.reset()

    def reset(self):
        self.s = []
        self.a = []
        self.r = []
        self.s2 = []
        self.ret = []

    def store(self, s, a, r, s2, ret):
        # store a transition to replay memory
        self.s.append(s)
        self.a.append(a)
        self.r.append(r)
        self.s2.append(s2)
        self.ret.append(ret)

    def get_len(self):
        return len(self.s)

    def get_last_transition(self):
        # return last stored transition
        return self.s[-1], self.a[-1], self.r[-1], self.s2[-1], self.ret[-1]


class Network():
    def __init__(self, env):
        self.env = env
        self.input_dim = len(env.observation_space.high)
        self.output_dim = env.action_space.n
        self.learning_rate = 0.008
        self.hidden_dim = 10

        self.graph = tf.Graph()
        with self.graph.as_default():
            tf.set_random_seed(1234)

            # input placeholders
            self.s = tf.placeholder("float", [None, self.input_dim])    # state
            self.a = tf.placeholder("float", [None, self.output_dim])   # action
            self.y = tf.placeholder("float")                            # return
            self.adv = tf.placeholder("float")                          # advantage

            # joint layers
            self.w = tf.Variable(tf.random_normal([self.input_dim, self.hidden_dim]))
            self.b = tf.Variable(tf.random_normal([self.hidden_dim]))
            self.h = tf.nn.tanh( tf.add(tf.matmul(self.s, self.w), self.b))

            # critic / value function
            self.w_v = tf.Variable(tf.random_normal([self.hidden_dim, 1]))
            self.b_v = tf.Variable(tf.random_normal([1]))

            self.value_pred = tf.matmul(self.h, self.w_v) + self.b_v
            self.v_loss = tf.reduce_mean(tf.pow(self.value_pred - self.y,2))

            # actor / policy optimization
            self.w_p = tf.Variable(tf.random_normal([self.hidden_dim, self.output_dim]))
            self.b_p = tf.Variable(tf.random_normal([self.output_dim]))

            self.policy = tf.nn.softmax(tf.matmul(self.h, self.w_p) + self.b_p)
            self.log_action_probability = tf.reduce_sum(self.a *  tf.log(self.policy))
            self.p_loss = -self.log_action_probability * self.adv

            # optimizers
            self.p_optim = tf.train.AdamOptimizer(self.learning_rate).minimize(self.p_loss)
            self.v_optim = tf.train.AdamOptimizer(self.learning_rate).minimize(self.v_loss)

            self.init = tf.initialize_all_variables()

        self.sess = tf.Session(graph = self.graph)
        self.sess.run(self.init)



import math
class Actor:
    def __init__(self, env, graph):
        self.env = env
        self.input_dim = len(env.observation_space.high)
        self.output_dim = env.action_space.n

        self.graph = graph



    def rollout_policy(self):
        """Rollout policy for one episode, update the replay memory and return total reward"""
        score = 0
        s = self.env.reset()
        ep_s = []
        ep_a = []
        ep_r = []
        ep_s2 = []
        ep_ret = []

        for time in range(200):
            a = self.choose_action(s)
            s2, r, done, _ = self.env.step(a)
            self.env.render()

            score += r
            if done or time >= self.env.spec.timestep_limit :
                break

            ep_s.append(s)
            ep_a.append(a)
            ep_r.append(r)
            ep_s2.append(s2)
            ep_ret.append(r)
            for i in range(len(ep_ret)-1):
                ep_ret[i] += r

            s = s2

        # for i in range(len(ep_ret)-2, 0, -1):
        #     ep_ret[i] += ep_ret[i+1]

        buff.store(ep_s, ep_a, ep_r, ep_s2, ep_ret)
        return score



    def update_policy(self, advs):
        #Update the weights by running gradient descent on graph with loss function defined
        global buff
        for s_batch, a_batch, adv_batch in zip(buff.s, buff.a, advs):
            for s, a, adv in zip(s_batch, a_batch, adv_batch):
                _, err_value = self.graph.sess.run([self.graph.p_optim, self.graph.p_loss],
                                             feed_dict={self.graph.s: s.reshape(1,4),
                                                        self.graph.a: self.to_action(a),
                                                        self.graph.adv: adv })

    def choose_action(self, s):
        softmax_out = self.graph.sess.run(self.graph.policy, feed_dict={self.graph.s: s.reshape(1,4)})
        # print(softmax_out)
        # sample action from prob density
        a = np.random.choice([0,1], 1, replace = True, p = softmax_out[0])[0]
        return a

    def to_action(self, idx):
        a = np.zeros((1, self.output_dim))
        a[0, idx] = 1
        return a




class Critic:
    def __init__(self, env, graph):
        self.env = env
        self.input_dim = len(env.observation_space.high)
        self.output_dim = env.action_space.n

        self.graph = graph
        self.discount = 0.90

        self.num_epochs = 20
        self.batch_size = 170

    def update_value_estimate(self):
        global buff
        #Monte Carlo prediction
        batch_size = min(buff.get_len(), self.batch_size)
        for _ in range(self.num_epochs):
            #Loop over all batches
            for i in range( buff.get_len()//batch_size ):
                batch_s, batch_y = self.get_next_batch(batch_size, buff.s, buff.ret)
                #Fit training data using batch
                self.graph.sess.run(self.graph.v_optim, feed_dict={self.graph.s: batch_s, self.graph.y: batch_y})


    def get_advantage(self, s_batch, r_batch, s2_batch):
        #Return TD(0) adv for particular state and action
        #Get value of current state
        advs = []
        for s, r, s2 in zip(s_batch, r_batch, s2_batch):
            s_value = self.graph.sess.run(self.graph.value_pred, feed_dict={self.graph.s: s.reshape(1,4)})
            s2_value = self.graph.sess.run(self.graph.value_pred, feed_dict={self.graph.s: s2.reshape(1,4)})
            # TD(0) for advantage
            advantage = r + self.discount * s2_value - s_value
            advs.append(advantage)
        return advs


    def get_next_batch(self, batch_size, states, returns):
        #Return mini-batch of transitions from replay data
        s = []
        r = []
        for i in range(len(states)):
            for j in range(len(states[i])):
                s.append(states[i][j])
                r.append(returns[i][j])
        s = np.array(s)
        r = np.array(r)
        idx =  np.random.randint(s.shape[0], size=batch_size)
        return s[idx,:], r[idx]



buff = Buffer()

env = gym.make('CartPole-v0')
env.seed(1234)
no_episodes = 2

graph = Network(env)
actor = Actor(env, graph)
critic = Critic(env, graph)

def run():
    advs = []
    sum_score = 0

    for i in range(1000):
        ep_score = actor.rollout_policy()
        sum_score += ep_score

        ep_s, ep_a, ep_r, ep_s2, ep_ret = buff.get_last_transition()
        advs.append( critic.get_advantage(ep_s, ep_r, ep_s2) )

        if (i+1) % no_episodes == 0:
            avg_score = sum_score / no_episodes
            print("to episode {} average score:  {}".format(i, avg_score))

            if avg_score >= 195:
                print("Passed")
            else:
                actor.update_policy(advs)
                critic.update_value_estimate()

            del advs[:]
            buff.reset()
            sum_score = 0

run()

