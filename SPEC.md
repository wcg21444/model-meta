# 模型文件元数据生成器

## 概述

    编写一个python+trimesh脚本,解析gltf 文件,生成指定Scheme的元数据(.meta.json)
    使用libclang作为 C++解析后端. C++的JSON后端是nlohmann/json

## 输出格式

    输出到模型文件的同级目录/<模型名>.modelmeta.json

## 元数据

```
    "model_type":"Skeletal"|"Static" //识别模型是否存在骨架骨骼
    "bouding_box":["min":float3,"max":float3] //模型包围盒,用于剔除
    "model_part": [
        {
            "model_name":<>,
            "bounding_box":<>
            "material":{
                "mat_name",
                "is_pbr",
                "textures":[
                    "base_color",
                    "metallic(optional)",
                    "roughness(optional)",
                    "normal(optional)",
                ]// 相对路径纹理槽位
                "alpha_mode": "Opaque"|"Cutout"|"Transparent",
                "roughness": 0.8,
                "metallic": 0.0
            }
        }
    ]
    "skeleton":[
        {
            "node_name",
            "model_part" :[<model_part_name in "model_part">]

        }
    ]// skeletal文件生成,用于生成物体节点层级架构
    "textures":[<pathes from all materials>],
    "material":[name from all model_part]
```

## 输出内容

- 元数据. <>.modelmeta.json
- 解包纹理图片 -> ./textures/ 或者参数指定路径
- c++ header,
- c++ 自动生成的序列化代码,在cpp中实现, 向Header暴露 T Parse(string jsonStr)函数接口

## scheme

- 将 C++ 结构和变量名与JSON字段的映射制成一张python表/字典(symbol_map.py), 允许用户修改字段映射表而不影响元数据生成逻辑.
- 当映射表发生改变,C++Scheme和序列化代码同步更新

## configs

- 配置(generator_configs.py)
  - 允许自定义命名空间,这由映射表实现. 可选值: none,<namespace>:指定命名空间
  - 指定命名规则:
    - 可选项: Big Camel ;Small Camel; snake; SCREAMING;
    - 针对字段: 变量字段|枚举名|命名空间|生成的函数签名
  - 浮点数截断位数 : none | number
  - 解包packin textures : bool
  - 解包输出路径: string
  - glob pattern :string
  - output path :string

## Cmake集成

## 依赖安装

```bash
pip install -r requirements.txt
```

## 使用方式

### 单文件模式

```bash
python gltf_meta_generator.py <模型.gltf|glb>
# 输出：同级目录下 <模型名>.modelmeta.json

# 指定输出路径
python gltf_meta_generator.py model.glb -o output.json
```

### Glob 批量模式

输入为 glob 模式时，`-o` 必须指向目录（以 `/` 或 `\` 结尾）。

```bash
python gltf_meta_generator.py "assets/**/*.glb" -o output_dir/
# 输出：output_dir/<文件名>.modelmeta.json
```

### 导出嵌入纹理 (--unpack)

将 GLTF/GLB 中内嵌的 Data URI / BufferView 纹理提取为文件，并在元数据中更新为相对路径。

```bash
python gltf_meta_generator.py model.glb --unpack
# 提取到 model.glb 同级 textures/ 目录，文件名带 <模型名>_ 前缀防冲突
```

### 自定义 Schema

```bash
python gltf_meta_generator.py model.glb --schema my_schema.json
```

输出格式由 `schema/modelmeta.schema.json` 驱动，不再硬编码。修改 Schema 后脚本自动适配。

---

## C++ 结构体导出 (libclang)

Schema 可同步导出为 C++17 头文件，结构名大驼峰、成员变量蛇形。

### 基础生成

```bash
python tools/schema_to_cpp.py schema/modelmeta.schema.json -o include/modelmeta.h
```

- 自动生成后调用 **libclang 验证**，确保语法 100% 合法
- 结构体按依赖关系**拓扑排序**，无需手动调整顺序

### 同步已有头文件

解析已有 `.h`，对比 Schema 差异后重写：

```bash
python tools/schema_to_cpp.py schema/modelmeta.schema.json -o modelmeta.h --sync modelmeta.h
```

取消所有CLI参数.用configs文件参数代替CLI参数. output_path不指定的默认行为: 在文件目录就地生成textures 和modelmeta.json.
