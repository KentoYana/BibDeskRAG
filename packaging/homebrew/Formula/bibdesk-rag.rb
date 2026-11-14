# TEMPLATE: Unreleased; render with tools/generate_formula.py before installation.
class BibdeskRag < Formula
  include Language::Python::Virtualenv

  desc "Read-only local literature retrieval for BibDesk libraries"
  homepage "@@HOMEPAGE@@"
  url "@@URL@@"
  version "@@VERSION@@"
  sha256 "@@SHA256@@"
  license "MIT"

  disable! date: "2026-11-01", because: "unreleased template; run tools/generate_formula.py"

  depends_on "pkgconf" => :build
  depends_on "libxml2"
  depends_on "libxslt"
  depends_on :macos
  depends_on "python@3.14"

  on_arm do
    depends_on macos: :sonoma
  end

  resource "build-wheels" do
    url "@@BUILD_URL@@"
    sha256 "@@BUILD_SHA256@@"
  end

  # BEGIN LOCKED RESOURCES
  resource "anyio" do
    url "https://files.pythonhosted.org/packages/a9/d2/f4d173e22df740bc37b1db102b386ba719b66e95b0f0d751f556b387e6d2/anyio-4.15.1.tar.gz"
    sha256 "9f28306018cbd6d329e64a36d58256edff76dd996fe423bc957326e578b82a94"
  end

  resource "arxiv" do
    url "https://files.pythonhosted.org/packages/03/b7/b574b73f269b0310f9ff134155ad22ec78aa41da64e6ff4a9ad0d1377949/arxiv-4.0.2.tar.gz"
    sha256 "08c152504c797fa70ad6a407374f865c3fa1f77c8f59d725da47916bac06236a"
  end

  resource "bibdeskparser" do
    url "https://files.pythonhosted.org/packages/29/9c/836d7d9149fcb76c9ae4c19849a212c5b94d9f0380fab897483b2d586eea/bibdeskparser-0.8.1.tar.gz"
    sha256 "4ce6a34d7d3aaea931e7bf884799f5a2444a9bba3c05064efaacd7f4459aea01"
  end

  resource "bibtexparser" do
    url "https://files.pythonhosted.org/packages/f4/37/e21f79f5116ad1fb92a8eb0e8a005cad59eb24660003982840daa6b9fafd/bibtexparser-2.0.0b9.tar.gz"
    sha256 "bcddf796cfe321bb92c17c844ca65d81731fb753a1dd0e82bc76a9947aa0f360"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/fd/11/b524cbd9bbdaca58608e4cf4053fd463417549e1959fa8d3aa18319f9555/certifi-2026.10.23.tar.gz"
    sha256 "a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/33/1c/f41d4e74c28ab327ff3acd36053f7ea506c55872d7a90b0fa71aa3ab0c89/charset_normalizer-3.5.2.tar.gz"
    sha256 "39de2a259fc954455c57274dc94c79d5842774e1247a016aff30bc0efed0f4ef"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/c7/0e/7fa0ef50764b67090eca4114772a2abf8b6148198475e54c660b97caeee6/click-8.5.0.tar.gz"
    sha256 "ba0d2089de75ea0310e2dde03160e6ca10009947fb95a182f9b54021bb272e34"
  end

  resource "defusedxml" do
    url "https://files.pythonhosted.org/packages/0f/d5/c66da9b79e5bdb124974bfe172b4daf3c984ebd9c2a06e2b8a4dc7331c72/defusedxml-0.7.1.tar.gz"
    sha256 "1bb3032db185915b62d7c6209c5a8792be6a32ab2fedacc84e01b52c51aa3e69"
  end

  resource "et-xmlfile" do
    url "https://files.pythonhosted.org/packages/d3/38/af70d7ab1ae9d4da450eeec1fa3918940a5fafb9055e934af8d6eb0c2313/et_xmlfile-2.0.0.tar.gz"
    sha256 "dab3f4764309081ce75662649be815c4c9081e88f0837825f90fd28317d4da54"
  end

  resource "h11" do
    url "https://files.pythonhosted.org/packages/01/ee/02a2c011bdab74c6fb3c75474d40b3052059d95df7e73351460c8588d963/h11-0.16.0.tar.gz"
    sha256 "4e35b956cf45792e4caa5885e69fba00bdbc6ffafbfa020300e549b208ee5ff1"
  end

  resource "habanero" do
    url "https://files.pythonhosted.org/packages/df/d6/c50bc0d3cd899145cdb0ce38641ae11bfbeaab6123c6e7e78f482570afb8/habanero-2.9.2.tar.gz"
    sha256 "efcdfecec965c413e0f1ee9034fbe955d42e6b815b0784aa0c4a3df2cc272019"
  end

  resource "httpcore" do
    url "https://files.pythonhosted.org/packages/06/94/82699a10bca87a5556c9c59b5963f2d039dbd239f25bc2a63907a05a14cb/httpcore-1.0.9.tar.gz"
    sha256 "6e34463af53fd2ab5d807f399a9b45ea31c3dfa2276f15a2c3f00afff6e176e8"
  end

  resource "httpcore2" do
    url "https://files.pythonhosted.org/packages/c0/61/afa9d6b7452f9eca73f73d45324eb0bb52f098fd5e6049bf6b8263be9b4e/httpcore2-2.16.0.tar.gz"
    sha256 "c72cd0413563b17e1cd8354677dff887466f8ec2551679759e93126534428643"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/b1/df/48c586a5fe32a0f01324ee087459e112ebb7224f646c0b5023f5e79e9956/httpx-0.28.1.tar.gz"
    sha256 "75e98c5f16b0f35b567856f597f06ff2270a374470a5c2392242528e3e3e42fc"
  end

  resource "httpx2" do
    url "https://files.pythonhosted.org/packages/43/73/5ca2cedf5e4e50423d1c258877865a6b62793633b561c58499f8aeb33b7e/httpx2-2.16.0.tar.gz"
    sha256 "0d54c98128e8f2ff7fbbde0fca8c359e5f032edeaaaac443cdb7f31f685bcd7f"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/f5/08/8eea9d4b8302028f3abb2c0813953f7aec26d33b7a8960ed760e65ff29fa/idna-3.20.tar.gz"
    sha256 "a7db850025b95ded1eae8a46181a1a6c56c92c96f0e2b005d9ff8dc0210cab44"
  end

  resource "lxml" do
    url "https://files.pythonhosted.org/packages/23/ad/28ecd7cb894d172f3c9c80a075eeeb2017ac62e3632cee05a5f9493547eb/lxml-6.1.3.tar.gz"
    sha256 "45222d94ddd511536f3b2f7d9deae3b2339b4ce0f075f1ca25703b07cad9dd21"
  end

  resource "olefile" do
    url "https://files.pythonhosted.org/packages/69/1b/077b508e3e500e1629d366249c3ccb32f95e50258b231705c09e3c7a4366/olefile-0.47.zip"
    sha256 "599383381a0bf3dfbd932ca0ca6515acd174ed48870cbf7fee123d698c192c1c"
  end

  resource "openpyxl" do
    url "https://files.pythonhosted.org/packages/3d/f9/88d94a75de065ea32619465d2f77b29a0469500e99012523b91cc4141cd1/openpyxl-3.1.5.tar.gz"
    sha256 "cf0e3cf56142039133628b5acffe8ef0c12bc902d2aadd3e0fe5878dc08d1050"
  end

  resource "packaging" do
    url "https://files.pythonhosted.org/packages/7d/fa/3944b40b07da9ce895c0e6303a5ab7d53da063554f534556b134a54d6093/packaging-26.3.tar.gz"
    sha256 "94edc256424af38762eb31306eed28beb9f0efc50a8837492c9d6fd6004aed79"
  end

  resource "pylatexenc" do
    url "https://files.pythonhosted.org/packages/52/45/ddb0fb04acf95fe9cf9c369814dbdd08651bd2c9ee455f142651e06f4488/pylatexenc-2.11.tar.gz"
    sha256 "305a072a99ce736246049c9da05841b9d718c0f7ea8888f5f596cf15cb621053"
  end

  resource "pypdf" do
    url "https://files.pythonhosted.org/packages/1e/e1/ec8f4d155c997c45917153a5521e60d6ee6389d68abdcbc8e44e564caffc/pypdf-6.21.4.tar.gz"
    sha256 "c8817e3f888d47a087872ded69812c1ef30cacb871d6e053e0c00bbaf0bc2163"
  end

  resource "pysocks" do
    url "https://files.pythonhosted.org/packages/bd/11/293dd436aea955d45fc4e8a35b6ae7270f5b8e00b53cf6c024c83b657a11/PySocks-1.7.1.tar.gz"
    sha256 "3f8804571ebe159c380ac6de37643bb4685970655d3bba243530d6558b799aa0"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-2.34.2.tar.gz"
    sha256 "f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed"
  end

  resource "socksio" do
    url "https://files.pythonhosted.org/packages/f8/5c/48a7d9495be3d1c651198fd99dbb6ce190e2274d0f28b9051307bdec6b85/socksio-1.0.0.tar.gz"
    sha256 "f88beb3da5b5c38b9890469de67d0cb0f9d494b78b106ca1845f96c10b91c4ac"
  end

  resource "tomli-w" do
    url "https://files.pythonhosted.org/packages/19/75/241269d1da26b624c0d5e110e8149093c759b7a286138f4efd61a60e75fe/tomli_w-1.2.0.tar.gz"
    sha256 "2dd14fac5a47c27be9cd4c976af5a12d87fb1f0b4512f81d69cce3b35ae25021"
  end

  resource "tqdm" do
    url "https://files.pythonhosted.org/packages/0d/ea/b2a5bd54b28a324dae8211928b2d730b6547500342c7e6c6dea08bd0a485/tqdm-4.70.1.tar.gz"
    sha256 "cefd0eca11b2a37a3aee776544d4f4ae913f02688135b5556b8788dfa474afc4"
  end

  resource "truststore" do
    url "https://files.pythonhosted.org/packages/ee/9f/c5201d42a484c061e528825fc8e2d565f5abd50a4ced6fb7d29c4ec99b2b/truststore-0.10.5.tar.gz"
    sha256 "30d36967ccaded5cbb38d602c433f53600036c79d502f4533a49b60a03bbefcd"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/f6/cc/6253133b5bb138fc3306cebfbda2c520f545d36b5be2c7255cc528bb45d6/typing_extensions-4.16.0.tar.gz"
    sha256 "dc983d19a509c94dba722ee6abd33940f7c05a89e243c47e907eb4db6f1a43e5"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/e3/05/b17359e1cefb4f909b5e40b1b90a496d987258916dbbf88e842c729f510e/urllib3-2.8.0.tar.gz"
    sha256 "63bf2ead4c879426ebf22ef2a781eeb4aa3b4ae798a0435506f8687fd5bb9b63"
  end

  resource "xlrd" do
    url "https://files.pythonhosted.org/packages/07/5a/377161c2d3538d1990d7af382c79f3b2372e880b65de21b01b1a2b78691e/xlrd-2.0.2.tar.gz"
    sha256 "08b5e25de58f21ce71dc7db3b3b8106c1fa776f3024c54e45b45b374e89234c9"
  end
  # END LOCKED RESOURCES

  # Runtime inputs are explicit sdists. Allow only the locked, offline backend
  # wheels during PEP 517 isolation; Homebrew otherwise forbids all wheels.
  def std_pip_args(**options)
    super.reject { |arg| arg.start_with?("--no-binary") }
  end

  def install
    backend_wheels = buildpath/"backend-wheels"
    resource("build-wheels").stage backend_wheels
    ENV["PIP_NO_INDEX"] = "1"
    ENV["PIP_FIND_LINKS"] = backend_wheels.to_s
    ENV["XML2_CONFIG"] = formula_opt_bin("libxml2")/"xml2-config"
    ENV["XSLT_CONFIG"] = formula_opt_bin("libxslt")/"xslt-config"
    venv = virtualenv_install_with_resources(system_site_packages: false, without: %w[build-wheels socksio])
    resource("socksio").stage do
      # Upstream flit 2 uses ast.Str, removed in Python 3.14. Only replace the
      # build backend requirement; the socksio runtime source is unchanged.
      inreplace "pyproject.toml", "flit_core >=2,<3", "flit_core ==3.12.0"
      venv.pip_install Pathname.pwd
    end
    if Hardware::CPU.arm?
      # Inference wheels are locked/verified in the same offline resource bundle.
      # Model weights are not included and are acquired only by explicit setup choice.
      manifest = JSON.parse((backend_wheels/"manifest.json").read)
      semantic_wheels = manifest.fetch("resources").select { |item| item["semantic_runtime"] }
      odie "Offline semantic wheels are missing" if semantic_wheels.empty?
      ENV["PIP_NO_DEPS"] = "1"
      venv.pip_install semantic_wheels.map { |item| backend_wheels/item.fetch("filename") }
      ENV.delete("PIP_NO_DEPS")
      system "python3.14", "-m", "pip", "--python", libexec/"bin/python", "check"
    end
    pkgshare.install "tools/package_smoke.py", "tools/format_fixtures.py"
  end

  def caveats
    <<~EOS
      Start the interactive setup in a terminal:
        bibdesk-rag --setup

      For an existing configuration in a custom location:
        bibdesk-rag --config use "/absolute/path/to/config.toml"
        bibdesk-rag --setup

      Setup registers your library, offers indexing, and checks the local MCP server.
      Existing configuration and indexes are retained unless you explicitly choose
      an index update or rebuild. Your BibDesk originals remain read-only.

      --index update/rebuild show terminal progress. Use --format json for a full report,
      --verbose for all diagnostics, or --no-progress to hide the bar.

      Codex CLI is optional: setup asks before registering the MCP server and shows
      manual app connection details if the CLI is unavailable or registration is skipped.
      Normal registration uses no arguments and follows the selected configuration.
      Only --temp PATH --setup pins a configuration in the registration.
      The MCP executable for manual connection is:
        #{opt_bin}/bibdesk-rag-mcp
      Restart Codex and ask it to use bibdesk-rag in a new chat.
      Manual setup and custom configuration paths:
        https://github.com/KentoYana/BibDeskRAG/blob/main/docs/codex.md

      To disconnect with the Codex CLI:
        codex mcp remove bibdesk-rag
      Then close active Codex/MCP sessions and uninstall BibDesk RAG:
        brew uninstall KentoYana/tap/bibdesk-rag

      Default configuration: ~/.config/bibdesk-rag/config.toml
      Default index: ~/.local/share/bibdesk-rag/index.sqlite3
      Apple Silicon includes local semantic inference in this same installation.
      In --setup, choose whether to use it and explicitly download the model.
      Index/search/MCP never download models. Do not pip-install into libexec.
      Semantic setup and offline operation:
        https://github.com/KentoYana/BibDeskRAG/blob/main/docs/semantic-search.md
      Existing custom locations are unchanged.
      Upgrades and uninstall do not remove them or modify your BibDesk originals.
      Optional data removal and removal without the Codex CLI:
        https://github.com/KentoYana/BibDeskRAG#アンインストール
    EOS
  end

  test do
    if Hardware::CPU.arm?
      system libexec/"bin/python", "-c", "import numpy, torch, sentence_transformers"
    end
    system libexec/"bin/python", pkgshare/"package_smoke.py",
           "--command", bin/"bibdesk-rag", "--mcp-command", bin/"bibdesk-rag-mcp",
           "--workdir", testpath/"smoke"
  end
end
