# ISSF 规则知识库系统 - API 接口文档

> 基础路径：`/api`
> 统一响应结构：
> ```json
> {
>   "success": true,
>   "code": "OK",
>   "message": "success",
>   "timestamp": 1718000000,
>   "data": {}
> }
> ```

---

## 1. 认证接口

### 1.1 登录
`POST /api/auth/login`

请求体：
```json
{
  "username": "admin",
  "password": "admin123"
}
```

响应：
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": { "id": "...", "username": "admin", "email": "admin@example.com", "role_id": "..." }
}
```

### 1.2 注册
`POST /api/auth/register`

请求体：
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "password123"
}
```

---

## 2. 规则查询接口（公开）

### 2.1 分页查询规则
`GET /api/rules?keyword=&category=&version=&page=1&page_size=10`

响应：
```json
{
  "success": true,
  "code": "OK",
  "data": {
    "items": [ { "rule_id": "RULE_2026_001", "title": "...", ... } ],
    "pagination": { "total": 1, "page": 1, "page_size": 10 }
  }
}
```

### 2.2 规则详情
`GET /api/rules/{rule_id}`

---

## 3. 管理后台接口（需 Bearer Token + admin 权限）

### 3.1 规则列表（含未发布）
`GET /api/admin/rules?keyword=&category=&version=&page=1&page_size=20`

### 3.2 创建规则
`POST /api/admin/rules`

请求体：
```json
{
  "rule_id": "RULE_2026_001",
  "title": "混合团体比赛计分规则",
  "category": "比赛规则",
  "version": "2026",
  "content": "...",
  "keywords": ["关键词1", "关键词2"],
  "is_published": true
}
```

### 3.3 更新规则
`PUT /api/admin/rules/{rule_id}`

请求体：
```json
{
  "title": "新标题",
  "content": "...",
  "is_published": false
}
```

### 3.4 删除规则（软删除）
`DELETE /api/admin/rules/{rule_id}`

### 3.5 看板统计
`GET /api/admin/dashboard`

响应：
```json
{
  "success": true,
  "code": "OK",
  "data": {
    "total_rules": 10,
    "total_qa": 128,
    "today_qa": 12,
    "week_qa": 45,
    "total_users": 3
  }
}
```

---

## 4. 系统接口

### 4.1 健康检查
`GET /api/health`

### 4.2 就绪检查
`GET /api/ready`

### 4.3 版本信息
`GET /api/version`

### 4.4 指标
`GET /api/metrics`

---

## 5. 问答接口

### 5.1 普通问答
`POST /api/ask`
```json
{ "question": "混合团体比赛取消赋分制后怎么计分？", "use_cache": true, "show_sources": false }
```

### 5.2 流式问答（SSE）
`POST /api/ask?stream=true`

响应头：`Content-Type: text/event-stream`

---

## 6. 认证说明

- 登录后获取 `access_token`
- 后续请求在 Header 中携带：`Authorization: Bearer <token>`
- admin 接口需要用户角色包含 `admin` 权限
