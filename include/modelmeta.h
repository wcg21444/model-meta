#pragma once

#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace GLTFModelMeta {

enum class AlphaMode {
  Opaque,
  Cutout,
  Transparent,
};
NLOHMANN_JSON_SERIALIZE_ENUM(AlphaMode, {
    {AlphaMode::Opaque, "Opaque"}, {AlphaMode::Cutout, "Cutout"}, {AlphaMode::Transparent, "Transparent"}
})

enum class ModelType {
  Skeletal,
  Static,
};
NLOHMANN_JSON_SERIALIZE_ENUM(ModelType, {
    {ModelType::Skeletal, "Skeletal"}, {ModelType::Static, "Static"}
})

struct BoundingBox {
  std::vector<float> min{};
  std::vector<float> max{};
};

struct TextureSlots {
  std::string base_color{};
  std::string metallic{};
  std::string roughness{};
  std::string normal{};
};

struct Material {
  std::string mat_name{};
  bool is_pbr{};
  TextureSlots textures{};
  AlphaMode alpha_mode{};
  float roughness{};
  float metallic{};
};

struct ModelPart {
  std::string model_name{};
  BoundingBox bounding_box{};
  Material material{};
  int mesh_index{};
};

struct SkeletonNode {
  std::string node_name{};
  std::vector<std::string> model_part{};
};

struct ModelMeta {
  std::string version{};
  ModelType model_type{};
  BoundingBox bounding_box{};
  std::vector<ModelPart> model_part{};
  std::vector<SkeletonNode> skeleton{};
  std::vector<std::string> textures{};
  std::vector<std::string> materials{};
};

ModelMeta Parse(const std::string& jsonStr);

} // namespace GLTFModelMeta
