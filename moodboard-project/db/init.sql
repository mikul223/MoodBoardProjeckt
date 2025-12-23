-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    username VARCHAR(50) UNIQUE NOT NULL,
    is_registered BOOLEAN DEFAULT FALSE,
    website_login VARCHAR(50) UNIQUE,
    hashed_password VARCHAR(255),
    plain_password VARCHAR(100)
);

-- Таблица досок
CREATE TABLE IF NOT EXISTS boards (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    view_token VARCHAR(50) UNIQUE NOT NULL,
    board_code VARCHAR(20) UNIQUE NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    background_color VARCHAR(20) DEFAULT '#FFFBF0',
    border_color VARCHAR(20) DEFAULT '#5D4037',
    board_width INTEGER DEFAULT 1200,
    board_height INTEGER DEFAULT 900,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner_id BIGINT REFERENCES users(id)
);

-- Таблица участников досок
CREATE TABLE IF NOT EXISTS board_members (
    board_id BIGINT REFERENCES boards(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(15) CHECK (role IN ('owner', 'collaborator')) NOT NULL,
    PRIMARY KEY (board_id, user_id)
);

-- Таблица контента
CREATE TABLE IF NOT EXISTS content_items (
    id BIGSERIAL PRIMARY KEY,
    board_id BIGINT REFERENCES boards(id) ON DELETE CASCADE,
    type VARCHAR(10) CHECK (type IN ('text', 'image')) NOT NULL,
    content TEXT NOT NULL,
    x_position INTEGER DEFAULT 0,
    y_position INTEGER DEFAULT 0,
    width INTEGER,
    height INTEGER,
    z_index INTEGER DEFAULT 1,
    media_metadata JSONB,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_website_login ON users(website_login);
CREATE INDEX IF NOT EXISTS idx_boards_owner_id ON boards(owner_id);
CREATE INDEX IF NOT EXISTS idx_boards_board_code ON boards(board_code);
CREATE INDEX IF NOT EXISTS idx_boards_view_token ON boards(view_token);
CREATE INDEX IF NOT EXISTS idx_content_items_board_id ON content_items(board_id);
CREATE INDEX IF NOT EXISTS idx_content_items_type ON content_items(type);
CREATE INDEX IF NOT EXISTS idx_content_items_z_index ON content_items(z_index);
CREATE INDEX IF NOT EXISTS idx_board_members_board_user ON board_members(board_id, user_id);
CREATE INDEX IF NOT EXISTS idx_board_members_role ON board_members(role);


COMMENT ON TABLE users IS 'Пользователи системы MoodBoard';
COMMENT ON TABLE boards IS 'Доски MoodBoard';
COMMENT ON TABLE content_items IS 'Элементы контента на досках';
COMMENT ON TABLE board_members IS 'Участники досок с ролями: owner (владелец), collaborator (соавтор)';


CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_content_items_updated_at
    BEFORE UPDATE ON content_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


INSERT INTO users (telegram_id, username, is_registered, website_login, hashed_password, plain_password)
VALUES (
    123456789,
    'test_user',
    TRUE,
    'test_login_001',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'password123'
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO boards (name, description, view_token, board_code, is_public, background_color, owner_id)
SELECT
    'Моя первая доска',
    'Тестовая доска для демонстрации',
    'test_token_001',
    'TEST001',
    TRUE,
    '#f0f0f0',
    id
FROM users
WHERE username = 'test_user'
ON CONFLICT (board_code) DO NOTHING;

INSERT INTO board_members (board_id, user_id, role)
SELECT
    b.id,
    u.id,
    'owner'
FROM boards b
JOIN users u ON u.username = 'test_user'
WHERE b.board_code = 'TEST001'
ON CONFLICT (board_id, user_id) DO NOTHING;

DO $$
BEGIN
    RAISE NOTICE '=========================================';
    RAISE NOTICE 'База данных MoodBoard инициализирована';
    RAISE NOTICE 'Новая структура:';
    RAISE NOTICE '- users';
    RAISE NOTICE '- boards';
    RAISE NOTICE '- board_members';
    RAISE NOTICE '- content_items';
    RAISE NOTICE '=========================================';
END $$;