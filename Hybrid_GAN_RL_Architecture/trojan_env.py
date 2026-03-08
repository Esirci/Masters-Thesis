import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class TrojanEnv(gym.Env):
    """
    Custom Environment that follows gym interface.
    The agent learns to classify hardware trojans.
    """
    metadata = {'render.modes': ['console']}

    def __init__(self, df):
        super(TrojanEnv, self).__init__()
        
        # Data handling
        # Assuming df has 'Label' as the target column
        self.labels = df["Label"].astype(int).to_numpy()
        self.features = df.drop("Label", axis=1).astype(np.float32).to_numpy()
        
        self.n_samples = len(self.labels)
        self.current_step = 0
        
        # Define action and observation space
        # Action: 0 (Non-Trojan) vs 1 (Trojan)
        self.action_space = spaces.Discrete(2)
        
        # Observation: The feature vector (size ~600)
        n_features = self.features.shape[1]
        self.observation_space = spaces.Box(
            low=-np.inf, 
            high=np.inf, 
            shape=(n_features,), 
            dtype=np.float32
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        # Optional: shuffle data on reset? For now, we iterate sequentially or random sample.
        # Stable baselines usually works well with random sampling or sequential if shuffled beforehand.
        # Let's start with index 0
        
        observation = self._get_observation()
        info = {}
        return observation, info

    def _get_observation(self):
        return self.features[self.current_step]

    def step(self, action):
        target = self.labels[self.current_step]
        
        # Calculate Reward
        # We specifically want to penalize False Positives (predicting 1 when truth is 0)
        # to lower the FPR (False Positive Rate).
        
        reward = 0
        terminated = False
        truncated = False
        
        if action == target:
            # Correct prediction
            reward = 1.0
        else:
            # Incorrect prediction
            if action == 1 and target == 0:
                # False Positive (Predicted Trojan, actually Clean)
                # CRITICAL: High penalty
                reward = -20.0 
            elif action == 0 and target == 1:
                # False Negative (Predicted Clean, actually Trojan)
                # Standard penalty
                reward = -1.0
        
        # Move to next sample
        self.current_step += 1
        
        if self.current_step >= self.n_samples:
            terminated = True
            # Loop back to 0 or just end? Ending episode is standard.
            # self.current_step = 0 
        else:
            observation = self._get_observation()
            return observation, reward, terminated, truncated, {}
            
        # If terminated, return dummy observation (reset will be called)
        return np.zeros(self.observation_space.shape, dtype=np.float32), reward, terminated, truncated, {}

    def render(self, mode='console'):
        if mode == 'console':
            print(f"Step: {self.current_step}")

    def close(self):
        pass
