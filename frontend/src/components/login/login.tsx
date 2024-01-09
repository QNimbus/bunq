import { useState } from 'react';
import classNames from 'classnames';
import styles from './login.module.scss';

export interface LoginProps {
    className?: string;
}

/**
 * This component was created using Codux's Default new component template.
 * To create custom component templates, see https://help.codux.com/kb/en/article/kb16522
 */
export const Login = ({ className }: LoginProps) => {
    const [state, setState] = useState({});

    return <div className={classNames(styles.root, className)}>Login</div>;
};
