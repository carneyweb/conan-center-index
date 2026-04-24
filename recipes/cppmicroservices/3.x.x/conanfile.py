import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get
from conan.tools.scm import Git
from conan.errors import ConanInvalidConfiguration, ConanException


class CppMicroServicesConan(ConanFile):
    name = "cppmicroservices"
    version = "3.8.10"
    description = "An OSGi-inspired dynamic module framework for C++"
    license = "Apache-2.0"
    url = "https://github.com/CppMicroServices/CppMicroServices"
    homepage = "https://cppmicroservices.org"
    topics = ("modularity", "runtime linking", "dependency inversion",
              "service oriented", "osgi", "microservices", "cross-platform")
    license = "Apache-2.0"
    no_copy_source = True
    settings = "os", "arch", "compiler", "build_type"

    # package_type = "library"

    options = {
        "shared":         [True, False],
        "fPIC":           [True, False],
        "with_threading": [True, False],
    }
    default_options = {
        "shared":         True,
        "fPIC":           True,
        "with_threading": True,
    }

    # Set this to None to build from the latest commit on the specified branch instead of a release tag.
    _dev_branch = "conan-support"

    @property
    def _build_compendium(self):
        # Upstream only adds the full compendium when threading + shared libs are both on.
        return bool(self.options.shared and self.options.with_threading)

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        os.environ["CMAKE_POLICY_VERSION_MINIMUM"] = "3.17"
        if self.settings.os == "Linux":
            os.environ["CXXFLAGS"] = "-Wno-maybe-uninitialized"
        if self.options.shared:
            self.options.rm_safe("fPIC")

        # Disable all compiled Boost libraries except nowide
        for opt_name in self.options["boost"].__dict__:
            if opt_name.startswith("without_") and opt_name != "without_nowide":
                setattr(self.options["boost"], opt_name, True)

        # In CppMicroServices we use the header-only version of Boost
        # self.options["boost"].header_only = True
        # self.options["boost"].without_nowide = True

    def layout(self):
        cmake_layout(self, src_folder="src")

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.17]")

    def requirements(self):
        # boost and cli11 link only into build-time tools (resource compiler,
        # code-gen); visible=False keeps them out of consumers' Conan graphs.
        #
        # miniz/spdlog/jsoncpp/rapidjson are baked into the installed shared
        # libraries, so consumers don't need to link them separately
        # (visible=False for shared).  For static builds consumers must link
        # them directly (visible=True).
        lib_visible = not bool(self.options.shared)
        self.requires("boost/1.86.0",            visible=False)
        self.requires("miniz/3.0.2",             visible=lib_visible)
        self.requires("spdlog/1.14.1",           visible=lib_visible)
        self.requires("jsoncpp/1.9.5",           visible=lib_visible)
        self.requires("rapidjson/cci.20220822",  visible=lib_visible)
        self.requires("cli11/2.4.1",             visible=False)

    def validate(self):
        check_min_cppstd(self, 17)

        # Mirror the minimum compiler versions enforced by upstream CMake.
        min_versions = {
            "gcc":         "7.5",
            "clang":       "9",
            "apple-clang": "10",
            # VS 2017 15.x (19.10) → Conan encodes as 191
            "msvc":        "191",
        }
        compiler = str(self.settings.compiler)
        min_ver = min_versions.get(compiler)
        if min_ver and str(self.settings.compiler.version) < min_ver:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires {compiler} >= {min_ver}, "
                f"got {self.settings.compiler.version}"
            )

    # source() is currently Git-based to support development builds from the tip of a branch.
    def source(self):
        git = Git(self)
        if self._dev_branch:
            # git.clone(url=self.url, args=["--recursive", "--branch",
            #          self._dev_branch, "--single-branch", "--depth", "1"], target=".")

            # Temporarily jsut copy from my local directory
            copy(self, "*", src="C:/Dev/CppMicroServices_Test",
                 dst=os.path.join(self.source_folder, "."))
        else:
            git.clone(url=self.url, args=[
                      "--recursive"], target="src")
            git.checkout(
                commit=self.conan_data["sources"][self.version]["sha1"])

            # Eventually we want to remove the Git-based source retrieval and switch to a simple
            # tarball download once the v3.8.10 tag exists, so we save the URL and commit in
            # conandata.yml and use get() here instead of git.clone().
            #
            # get(self,
            #    url=f"https://github.com/CppMicroServices/CppMicroServices/archive/refs/tags/v{self.version}.tar.gz",
            #    sha256="PLACEHOLDER_fill_in_once_v3.8.10_tag_exists",
            #    strip_root=True)

    # generate is where we set CMake variables and generate both the CMakeToolchain and CMakeDeps files.
    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["CMAKE_BUILD_TYPE"] = str(self.settings.build_type)
        tc.variables["BUILD_SHARED_LIBS"] = self.options.shared
        tc.variables["US_ENABLE_THREADING_SUPPORT"] = self.options.with_threading
        # Always use Conan-provided packages instead of the bundled third_party/ copies.
        tc.variables["US_USE_SYSTEM_BOOST"] = True
        tc.variables["Boost_NO_BOOST_CMAKE"] = False
        tc.variables["US_USE_SYSTEM_MINIZ"] = True
        tc.variables["US_USE_SYSTEM_SPDLOG"] = True
        tc.variables["US_USE_SYSTEM_JSONCPP"] = True
        tc.variables["US_USE_SYSTEM_RAPIDJSON"] = True
        tc.variables["US_USE_SYSTEM_CLI11"] = True
        # Never pull in test or example build-time deps in a package recipe.
        tc.variables["US_USE_SYSTEM_GTEST"] = False
        tc.variables["US_BUILD_TESTING"] = False
        tc.variables["US_BUILD_EXAMPLES"] = False
        # Set CMAKE_DEBUG_POSTFIX to "" to avoid upstream's default "d" suffix on debug builds,
        # which would break Conan's package ID consistency between build types.
        tc.variables["CMAKE_DEBUG_POSTFIX"] = ""
        # prefer config over find module
        tc.variables["CMAKE_FIND_PACKAGE_PREFER_CONFIG"] = True
        tc.generate()

        deps = CMakeDeps(self)
        # Align generated cmake_file_name / cmake_target_name with what the upstream
        # CMake code uses after find_package().
        deps.set_property("cli11",     "cmake_file_name",   "CLI11")
        deps.set_property("cli11",     "cmake_target_name", "CLI11::CLI11")
        deps.set_property("rapidjson", "cmake_file_name",   "rapidjson")
        deps.set_property("rapidjson", "cmake_target_name",
                          "rapidjson::rapidjson")
        deps.set_property("jsoncpp",   "cmake_file_name",   "jsoncpp")
        deps.set_property("jsoncpp",   "cmake_target_name", "jsoncpp::jsoncpp")
        deps.set_property("miniz",     "cmake_file_name",   "miniz")
        deps.set_property("miniz",     "cmake_target_name", "miniz::miniz")
        deps.set_property("spdlog",    "cmake_file_name",   "spdlog")
        deps.set_property("spdlog",    "cmake_target_name", "spdlog::spdlog")
        deps.generate()

    # build / package are where we call CMake to build and install the library.  The upstream
    # CMakeLists.txt is already set up to install everything correctly, so we don't need to do any
    # manual copying here.
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "LICENSE",
             src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))

    # package_info is where we define the components and their properties for consumers.
    #
    # The upstream CMakeLists.txt defines three components: the core framework (CppMicroServices),
    # the LogService API (usLogService), and the full compendium of built-in bundles
    # (AsyncWorkService, DeclarativeServices ConfigurationAdmin, etc.).  The framework is always
    # present, the LogService API is always built alongside it, and the full compendium is only
    # built when both threading and shared options are enabled.
    def package_info(self):
        major = self.version.split(".")[0]  # "3"
        cmake_dir = os.path.join("share", f"cppmicroservices{major}", "cmake")
        helpers = os.path.join(cmake_dir, "CppMicroServicesHelpers.cmake")

        # "config" mode: Conan generates a CppMicroServicesConfig.cmake wrapper
        # that consumers reach with find_package(CppMicroServices).
        # cmake_build_modules is included after targets are defined; it exposes
        # the bundle-authoring API (usFunction* helpers, usResourceCompiler target,
        # template paths) without consumers needing to know any install paths.
        self.cpp_info.set_property("cmake_find_mode",     "config")
        self.cpp_info.set_property("cmake_file_name",     "CppMicroServices")
        self.cpp_info.set_property("cmake_build_modules", [helpers])

        lib_dir = os.path.join(self.package_folder, "lib")

        def find_lib(prefix):
            # Find the actual installed lib name matching a prefix
            for f in os.listdir(lib_dir):
                name = os.path.splitext(f)[0]  # strip .lib/.a
                if name.startswith(prefix):
                    return name
            raise ConanException(
                f"Could not find lib with prefix '{prefix}' in {lib_dir}")

        # framework
        #
        # The framework output name includes the version-major suffix on Windows
        # only (see usMacroCreateBundle.cmake).
        fw_lib = f"CppMicroServices{major}" if self.settings.os == "Windows" \
            else "CppMicroServices"

        fw = self.cpp_info.components["framework"]
        fw.set_property("cmake_target_name", "CppMicroServices")
        fw.libs = [fw_lib]
        fw.includedirs = [f"include/cppmicroservices{major}"]

        if self.settings.os == "Windows":
            fw.system_libs = ["shlwapi"]
        elif self.settings.os == "Linux":
            fw.system_libs = ["dl"]

        if self.options.with_threading and self.settings.os != "Windows":
            fw.system_libs.append("pthread")

        # LogService
        ls = self.cpp_info.components["logservice"]
        ls.set_property("cmake_target_name", "usLogService")
        ls.libs = [find_lib("LogService")]
        ls.requires = ["framework"]

        # Full compendium (threading=ON and shared=ON only)
        #
        # Each bundle carries its own semantic version; the version-major suffix
        # in the Windows output name reflects that bundle's major, not 3.x.x.
        # For CMake consumers the project's own targets are authoritative.
        if self._build_compendium:
            bundles = {
                # component key         : (cmake target,        output name on Unix)
                "logserviceimpl":        ("LogService",          find_lib("LogService")),
                "asyncworkservice":      ("usAsyncWorkService",  find_lib("usAsyncWorkService")),
                "servicecomponent":      ("usServiceComponent",  find_lib("usServiceComponent")),
                "declarativeservices":   ("DeclarativeServices", find_lib("DeclarativeServices")),
                "configurationadmin":    ("ConfigurationAdmin",  find_lib("ConfigurationAdmin")),
                "eventadmin":            ("usEM",                find_lib("usEM")),
            }
            for comp_name, (cmake_tgt, lib_name) in bundles.items():
                comp = self.cpp_info.components[comp_name]
                comp.set_property("cmake_target_name", cmake_tgt)
                comp.libs = [lib_name]
                comp.requires = ["framework"]
