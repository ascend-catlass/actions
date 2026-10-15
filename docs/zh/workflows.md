# �������������� Actions

[����](../zh/workflows.md) �� [English](../en/workflows.md)

Action ���һ���ɸ��ò��裬�������Ѷ�������ų��������̡�������ֿܲ����е�ҵ��������CANN ��װ������ͬ��������ֱ�ӵ��ýű���û�ж����װΪ�Զ��� Action��

## ������Ŀ¼

| ������ | ��ʲô | ʲôʱ������ |
| --- | --- | --- |
| [test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml) | �ϲ������� AtomGit PR����д�� RDV ״̬ | �ֶ�ָ�� PR ��� |
| [reply-atomgit-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-ci-passed.yml) | CI ͨ�����ͼ������� | �ֶ������ͨ����ǩ |
| [reply-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-issue.yml) | �ǽ�ɫ��Ա Issue ��Ҫ������TRAE CN�� | �ֶ� |
| [fix-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/fix-atomgit-issue.yml) | �� Issue �޸����� PR������ compile��TRAE CN�� | ���ֶ� |
| [review-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/review-atomgit-pr.yml) | �Ա���з������������TRAE CN�� | ���ֶ� |
| [build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml) | ׼����ǰ���ڻ��ߵ� NPUIR �����鵵 | �ֶ����������������� |
| [build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml) | ������ NPUIR ���ڻ��ߣ�����ʷ���ⶨλ | �ֶ����������������� |
| [build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml) | ���� x86_64��aarch64 �� DSL wheel ��������� | �ֶ��� nightly/release ���� |
| [nightly-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/nightly-dsl-wheel.yml) | ���������汾�������� GitHub Release ֧�ŵİ����� | ÿ�ձ���ʱ�� 01:00�����ֶ� |
| [release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml) | У���ȶ� tag�������������� PyPI �� AtomGit Release | �ֶ� |
| [install-cann-weekly.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/install-cann-weekly.yml) | ��װͬһ�����汾�� CANN weekly ������ CPU �ܹ����� | ÿ�ձ���ʱ�� 02:00�����ֶ� |
| [sync-atomgit.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/sync-atomgit.yml) | �� AtomGit `master` �� tags ����ͬ���� GitHub | ÿ�ձ���ʱ�� 02:00�����ֶ� |

��ʱ����ʽʹ�� UTC�������ѻ���Ϊ����ʱ�䡣��ʱ�����ʵ�����������Ŷӡ�ҵ�� job ��Ҫ�� `main` ��֧���ֶ�ѡ��������֧����ִ��ҵ������PR ���ֻ���Ժ͹����ĵ������������ۡ�

## PR ����

1. [atomgit-pr-metadata](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/atomgit-pr-metadata) ��ѯ PR ��֧����Դ�ύ��
2. [rdv-status](actions/rdv-status.md) д����Կ�ʼ״̬��
3. GitHub-hosted runner ����Ŀ���֧�� PR�����޸�·�����ࡣֻ���ĵ���ͼƬ���ʱ�ڴ���ɣ������� Ascend 950��
4. ���������� `ascend950` ���й� runner �ϲ�����ȡ���� PR head ���ѯ�����ͬ��ϲ���ͻʱ��ʧ�ܡ�
5. [create-ascend-container](actions/create-ascend-container.md) ׼��������[prepare-ci-tests](actions/prepare-ci-tests.md) ��װ���˺��������ѡ����
6. [run-ci-tests](actions/run-ci-tests.md) ִ������׶Σ�DSL ���ν��� dev ������IR/Lit ���Ժ��豸���ԣ��� DSL ������뷴��ͷ�ļ�����ѡ����ԡ����඼�޸������඼���С�
7. ������ RDV ��׼���׶λ���� job ʧ�ܻ����������� GitHub �йܷ��� job������ͨ�õ� [`analyze-ci-failure`](actions/analyze-ci-failure.md)�����뵱ǰ���б���� attempt��Action �ڸ��ùٷ� `actions/github-script` ��ȡ��־��[`setup-trae-cn`](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/setup-traecn) ��װ CLI��`trae-cn` ִ�� DeepSeek-V4.1-Flash ������������С�ű�������־ժȡ��������������װ�����ԭ�����ݺ���һ�����顣��װ Action Ҳ�� Issue �������޸��� PR ���ӹ��á��������ִ�� PR ���롣
8. ���� job ������׷����ԭ RDV Failed ���۵����������£����� job ��ʱ��ģ��ʧ�ܻ���־������ʱ���ӡ������ݲ����á������������� RDV-FAIL���ɹ���ȡ�������۱���ԭ�������� job � 12 ���ӣ�ģ��ִ��Ԥ�� 5 ���ӣ����۸����������졣���������� `always()` ���账����

�����ظ������ķ�ʽ�ǹ���׼�����衢���� DSL dev �����������ѡ����ԣ��Լ�����־�����Զ�д�� PR������ѡ��Χ��[Դ��˵��](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)��

## ��������Э����ˮ��

### 1. Issue ��Ҫ�������Զ���TRAE CN��

Action ��ȡ�����ֿ�����½�ɫ���������� Committer/ά�������ߣ����Զ����䡣���� Issue ��ȡԴ������ۣ�TRAE CN ʹ�� DeepSeek-V4.1-Flash ������̷���������ǰ�����ɫ�����ۣ����»򴴽����˺ŵ�һ���ظ���

�ֶ����ܣ�ѡ�� **Community 1**����д `issue_url`��`publish=false` ֻ���ɷ������������ۡ�����������졣

### 2. PR CI ͨ����ظ����Զ������� PR��

�ֶ�ָ�� PR ��š�Action Ҫ�� PR �Կ����Һ� `ci-pipeline-passed` ��ǩ��PR ���߽�ɫ��Ӱ��ظ��ʸ�

Action ��ѯ��ǰ״̬����ҳ���ز����ͼ������ѣ�ͬһ PR ����ִ�С�����Ĳ�ѯ���ڷ���ǰ��ֹ״̬�仯���ֶ����ܣ�ѡ�� **Community 2**����д `pr_number`��

### 3. �� Issue �����޸������ֶ���TRAE CN��

ѡ�� **Community 3**����д `issue_number` �� `validation_command`�����Ƕ�����ά�����ֶ��������Ҫ�����ظ�û���������ഥ����ϵ�������ȷ�������Ҫ�����лظ���Ҳ������ Issue ���߽�ɫ��

1. �̶� CATLASS master Դ��� Issue ���ۿ��ա�
2. TRAE CN ֻ��������������Ƿ�򵥡��޸�˵���� unified patch�����ӻ���ȷ���������Ϊ `needs-human`������ PR��
3. ��������У�鲢Ӧ�ò��������ʮ���ļ����������Զ������á�symlink ����ģ���޸ģ�ִ��ά����ָ����֤�����֤���費���շ���ƾ�ݡ�
4. ��֤ͨ��������δ�仯�������������˺����е� CATLASS ���� fork �� `codex/issue-*` ��֧������ `cann/catlass:master` �� PR��
5. �ز� PR �󷢲�һ��׼ȷ�� `compile` ���ۣ��������в��ԣ�����ʱ�����Ѵ����� PR �����ۡ�

���л����� GitHub Linux runner���� NPU����֤�����������Ҫ����׼������Ӧ��������޸������� `python3 -m pytest tests/path/to/test_case.py`����Ҫ�豸����ȷ�ϵ����⽻���˹������������˺ŵ� AtomGit Token ���� fork ���͡����� PR ������Ȩ�ޡ�

### 4. PR �м����ӣ����ֶ���TRAE CN��

ѡ�� **Community 4**����д `pr_number`���̶� PR head/base����ȡ diff �����Դ�롣ģ��ֻ�����д������ݵ����ʣ����ʮ������������Ҫ��ÿ����Ӧ��ǰ diff ������/�޸��У����ܰ���ͨ���۵����м����ӡ�PR ���º�ܾ����������������У���ͬ�汾����ͬ�������Բ��ظ����ۡ��޷���ʱ�������������������ۣ�Ҳ���Զ���׼��ϲ���

ʹ�� AtomGit [�м����۽ӿ�](https://docs.atomgit.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/)��������ز��������ġ����ߡ��ļ��� head�������ͷ���֤�ݱ������졣

## �����鵵�� wheel �ַ�

DSL �������� 124��125 ��̨������ɡ���Ϊ����̨���������� runner ����ר�ñ�ǩ `ascend-catlass-dsl-build`������Ĭ�ϵ� `self-hosted`��`Linux` ��ʵ�ʼܹ� `X64`/`ARM64` ��ǩ��`build-dsl-wheel.yml` �� `build-ascendnpu-ir-20261013.yml` ʹ����ͬ��ר�ñ�ǩ�ͼܹ�ɸѡ��ʹ����׼���� wheel ����ʹ��ͬһ̨�����ı��ع鵵��ÿ�ּܹ�ֻ����һ̨���ϱ�ǩ�����������������ṩ�����鵵����ʽ�󶨻������ϲ����ȱ��ǰ��ȷ����̨ runner ���ߣ����߱� Docker������ CANN �͹鵵Ŀ¼����Ȩ�ޡ�nightly/release �Զ����ô˹����أ���ʷ NPUIR 20260720 �� AtomGit ��������ʹ�� `publish`��

NPUIR ��ÿ̨�������ϱ������ڹ鵵��[npuir-local-archive](actions/npuir-local-archive.md) �ȼ��Դ���ύ���ܹ��빹��Լ��������ʱֱ�Ӹ��ã�ȱʧʱ�ɹ��������롣`latest` ֻǰ�ƣ�wheel ������ѡ��ƥ�� CATLASS gitlink ��׼ȷ������

wheel �������� x86_64 �� aarch64 �����Ϲ�����nightly ���������汾�� GitHub ��������release �ȼ�� AtomGit �ȶ� tag���ٷ����� PyPI �� AtomGit��AtomGit �ַ�ʹ�� [atomgit-release](actions/atomgit-release.md)��������ͬ�����ɸ��ã�`artifact_run_id` ��ѡ�����з������е���֤����������¹�����

## ������װ�뾵��ͬ��

CANN weekly ����������ͬһ�ٷ��������ٷֱ��� X64 �� ARM64 `bz` ������װ Toolkit ���ӦоƬ�� ops����װ·��Ϊ `/opt/cann_weekly/YYYYMMDD`���ѳɹ������ڰ�װ��������`latest` ָ�����Ŀ¼����װ�������������̼�����־���� 30 �졣

����ͬ���� `cann/catlass` �� AtomGit �ֿ���ȡ `master` �� tags��Ȼ��ǿ�Ƹ��� GitHub `ascend-catlass/catlass` ��Ӧ��֧���ǩ�������������ٴ��ڵ� tag�����Ӧ��Ŀ��ֿ���Ϊ����ʹ�á�

## ʹ��ʱ��Ҫ��Щƾ��

| ƾ�ݻ����� | ʹ������ |
| --- | --- |
| `ATOMGIT_TOKEN`��Ϊ��ʱ���� `GITCODE_TOKEN` | PR Ԫ���ݡ����ۺͱ�ǩ��Issue ��ȡ�뷢����AtomGit Release����ʹ�÷�Χ����Ȩ�� |
| `TRAE_CN_PAT` | TRAE CLI ��ҵ��¼������ TestPR ʧ�ܷ��� |
| `TRAE_CN_HOST` | ��ѡ����ҵ�����ַ���� |
| `CATLASS_DEPLOY_KEY` | д�� GitHub ����ֿ� |
| PyPI Trusted Publisher | �ȶ��汾�� PyPI �������� `pypi` ������ release ������ |

Token ͨ�� Secret ������Ҫ���Ĳ��裻��Ҫ�Ž�Դ�롢��ʾ�ʻ����ʾ���е���ͨ�ı���

## ���� Action ����

ͨ�ò������� `yuantao313/actions` �Ĺ̶��ύ `fbfd9b229556d974d5aee35dafdf9dffe976facd`��RDV ״̬����ʹ���޸��汾 `38c9c6b54de142c3120e000f1e4cdff84970bf47`��CATLASS Python ������Ҫ���� helpers ʱ����������ͬһ�汾����� `shared_actions`�����غ��Ը�Ŀ¼������ʵ�ּ��䵥Ԫ����������ά����

ƾ�����ȶ�ȡ `ATOMGIT_TOKEN`��δ���û�Ϊ��ʱ���˵�ԭ�� `GITCODE_TOKEN`�������������������������������ԭ�б�ʶ `gitcode-release` ����Ȩ�����á�����������ļ���ͳһΪ `atomgit` ���ơ���ʷ NPUIR 20260720 ���������Ϊ������������������ƽ̨��ν��
