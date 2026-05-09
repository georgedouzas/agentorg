import { useState, KeyboardEvent } from 'react';
import { getRecentUsers } from '../../hooks/useIdentity';
import styles from './LoginScreen.module.css';

interface LoginScreenProps {
  appName: string;
  appIcon: string;
  appDescription: string;
  onLogin: (name: string) => void;
}

export function LoginScreen({ appName, appIcon, appDescription, onLogin }: LoginScreenProps) {
  const [name, setName] = useState('');
  const recentUsers = getRecentUsers();

  function handleSubmit() {
    const trimmed = name.trim();
    if (trimmed) onLogin(trimmed);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') handleSubmit();
  }

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <div className={styles.icon}>{appIcon}</div>
        <h1 className={styles.title}>{appName}</h1>
        <p className={styles.description}>{appDescription}</p>

        {recentUsers.length > 0 && (
          <div className={styles.recentSection}>
            <p className={styles.recentLabel}>Recent users</p>
            <div className={styles.recentPills}>
              {recentUsers.map(user => (
                <button
                  key={user}
                  className={styles.pill}
                  onClick={() => onLogin(user)}
                >
                  {user}
                </button>
              ))}
            </div>
            <div className={styles.divider}>
              <span>or enter a name</span>
            </div>
          </div>
        )}

        {recentUsers.length === 0 && (
          <p className={styles.enterLabel}>Enter your name to continue</p>
        )}

        <div className={styles.inputRow}>
          <input
            className={styles.input}
            type="text"
            placeholder="Your name"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button
            className={styles.enterBtn}
            onClick={handleSubmit}
            disabled={!name.trim()}
          >
            Enter
          </button>
        </div>
      </div>
    </div>
  );
}
