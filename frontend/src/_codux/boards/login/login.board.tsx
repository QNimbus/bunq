import { createBoard } from '@wixc3/react-board';
import { Login } from '../../../components/login/login';

export default createBoard({
    name: 'Login',
    Board: () => <Login />,
    isSnippet: true,
});
