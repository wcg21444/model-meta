# TODO

## 规范Model Part 和Mesh引用

## unpack覆盖机制

unpack Textures, 覆盖已有文件? 提供unpack policy: cover | retain

## 版本号

### 配置文件版本号机制


### 元数据版本号机制

元数据格式版本号与Schema,Cpp CodeGen 版本号挂钩

版本号：MAJOR.MINOR.PATCH，记录在项目根目录的 VERSION 文件或 pyproject.toml。
MAJOR：生成数据 Schema 不兼容变更（如 required 字段增删、类型改变）。
MINOR：新增可选字段、新的生成选项、性能改进（不破坏既有格式）。