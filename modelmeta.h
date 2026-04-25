#pragma once
#include <string>
#include <vector>
#include <array>
#include <optional>

namespace modelmeta {

enum class ModelType;
enum class AlphaMode;

// Axis-aligned bounding box
struct BoundingBox {
    std::array<float, 3> min;
    std::array<float, 3> max;
};

// Relative texture path mapping
struct TextureSlots {
    std::optional<std::string> albedo;
    std::optional<std::string> metallic;
    std::optional<std::string> roughness;
    std::optional<std::string> normal;
};

// A joint/bone node in the skeleton hierarchy
struct SkeletonNode {
    std::string node_name;
    std::vector<std::string> model_part;
};

// PBR material descriptor
struct Material {
    bool is_pbr;
    TextureSlots textures;
    enum class AlphaMode {
        OPAQUE,
        CUTOUT,
        TRANSPARENT,
    };

    AlphaMode alpha_mode;
    float roughness;
    float metallic;
};

// A single mesh part with its own material
struct ModelPart {
    std::string name;
    std::optional<BoundingBox> bounding_box;
    Material material;
};

// Root metadata object for a GLTF/GLB model
struct ModelMeta {
    enum class ModelType {
        STATIC,
        SKELETAL,
    };

    ModelType model_type;
    BoundingBox bounding_box;
    std::vector<ModelPart> model_part;
    std::vector<SkeletonNode> skeleton;
};

} // namespace modelmeta
