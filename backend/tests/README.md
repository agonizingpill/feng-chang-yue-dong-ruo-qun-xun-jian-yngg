# 越冬季回归测试

```sh
cd backend
PYTHONPATH=. python -m pytest tests -q                       # SQLite，默认
TEST_DATABASE_URL='postgresql+psycopg://apiary:apiary@localhost:17726/apiary' \
  PYTHONPATH=. python -m pytest tests -q                     # PostgreSQL
```

`TEST_DATABASE_URL` 指向的库会被 `drop_all` 清空，务必使用临时库。设置后额外运行旧库升级测试。
`fakeredis` 只用于让筛查队列在测试里可用，缺失时队列相关用例不可用，其余用例照常运行。
