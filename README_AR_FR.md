# Épicerie Enterprise V39 — مراجعة قبل إغلاق الصندوق

## جديد
- دمج فحص `cash_reconciliation.inspect` داخل زر إغلاق الصندوق.
- يمنع الإغلاق عند وجود تحذيرات عن طرق الدفع أو الشيكات أو المرتجعات التي تحتاج إلى مراجعة.
- عند عدم وجود تحذيرات، يعرض الرصيد النقدي التقديري والفرق ويطلب تأكيداً صريحاً قبل الإغلاق.
- لا يدعي أن دفتر الصندوق القديم مكتمل؛ ما زال الإغلاق القديم يعتمد حساباً مختلفاً، ولذلك تظهر رسالة تحذيرية.

## تشغيل Windows
استخدم `BUILD_ON_WINDOWS.bat` على حاسوب إعداد Windows مثبت عليه Python. الحزمة ليست EXE جاهزاً.
احتفظ بنسخة احتياطية من قاعدة البيانات قبل أي ترقية. لا تستخدمها كبديل لمراجعة الصندوق اليدوية.

## Français
Le contrôle de rapprochement est intégré à la clôture de caisse. Les anomalies bloquent la clôture. Sans anomalie, une confirmation explicite est exigée. Les calculs historiques de clôture ne sont pas encore unifiés : version de test uniquement.

## V40 — Verified cash close / إغلاق الصندوق الموحد
- `verified_close.py`: atomic verified closing; the recorded expected cash is identical to `cash_reconciliation.inspect()` preview.
- GUI closes through `close_verified()` instead of the legacy `close_cash()` calculation.
- Blocks unresolved attribution warnings, negative counted cash, duplicate closing, and cashier access.
- Five new tests in `tests/test_v40_verified_close.py` (152 total passing).
- Existing legacy close_cash API remains for compatibility; use verified close in the GUI.
- Still not a certified accounting ledger: some historic cash methods and refunds remain ambiguous and deliberately block verified closing.

## V41 — Partial-return cash safety / سلامة المرتجعات الجزئية
- The cash close readiness inspection now detects partial returns after the cash session opened.
- Because the legacy cash snapshot excludes partial refunds and does not record their actual payment method, verified close is blocked rather than presenting a potentially incorrect cash balance.
- Three regression tests verify blocking, normal cash sales, and read-only inspection (155 tests passed).
- This is a protective check, not a complete unified cash ledger. A Windows EXE installer has not been built or tested here.

## V42 — Sale line integrity / مطابقة المبيعات
- قبل إغلاق الصندوق، يتحقق الفحص من وجود أسطر لكل فاتورة بيع ومن تطابق مجموع (الكمية × ثمن الوحدة) مع إجمالي الفاتورة.
- عند اكتشاف خلل، يُمنع الإغلاق الموثق بدلاً من اعتماد رصيد يحتمل أن يكون خاطئاً.
- فحص للقراءة فقط؛ لا يُصلح السجلات تلقائياً ولا يغيّر أرصدة المحل.
- لا يزال ملف EXE النهائي يحتاج إلى البناء والاختبار على Windows.

## V43 — Cash payment and refund integrity / سلامة الأداء والمرتجعات
- Before verified close, check cash sale received minus change equals sale total, and reject negative tender/change fields.
- Detect aggregate full/partial refunds greater than the original sale total.
- Five new unit tests, total 164 passing on development environment.
- These are read-only integrity checks; they do not replace a unified payment ledger or Windows hardware testing.

## V44 — Cash payment state integrity / سلامة حالات الدفع النقدي
- Inspect pending or rejected customer cash payments and supplier cash settlements, including unsettled supplier records with no settled_at timestamp.
- Flag legacy negative expense amounts before verified closing.
- Read-only checks, with four regression tests (168 tests passing).
- No native Windows EXE was produced or tested in this environment.

## V45 — Cash movements / حركات الصندوق
- `cash_movements.py`: read-only itemized cash register for the open session; signed integer centimes and reconciliation against existing cash snapshot.
- CSV export includes each movement, expected balance, readiness flag and warnings. Refuses overwriting existing reports.
- GUI: `حركات الصندوق / Mouvements` button.
- Five regression tests added (173 tests passed in Linux development environment).
- This is NOT a unified accounting ledger: legacy payments, partial refunds and unspecified payment methods remain unresolved. No Windows installer has been tested.


## V46 - Cash close integrity
- Warns on collected supplier cash settlements with missing settlement timestamp.
- Warns when expense payment method is unknown (cash assumed in snapshot).
- Warns on negative legacy cash opening balances.
- These are conservative advisory checks: legacy records must be reconciled before certified closure.


## V47 — Payment methods for expenses / طرق أداء المصاريف
- Explicit cash, bank or cheque payment method in the finance UI and database.
- Database migration retains old expenses as `unknown`; unknown entries still count in advisory cash but block verified closing until reconciled.
- Bank and cheque expenses do not reduce physical cash, while all expenses still reduce operating profit.
- The legacy close_cash method is preserved for backward compatibility; the GUI uses verified close.
- No Windows installer built or tested here.

## V48 — Full refund payment methods / وسائل رد المبالغ
- Full sale refunds now record `refund_method`: cash, bank, cheque, or unknown (legacy).
- Cash snapshot and movement CSV deduct only cash/unknown refunds; bank and cheque refunds do not reduce cash on hand.
- Verified closing blocks unknown refund methods; the GUI defaults to explicit cash selection.
- Historical refunds migrate to unknown, preserving data and conservative warnings.
- Partial returns still require method attribution and block verified closing.
- This is a development build kit, not a tested Windows EXE.


V49: Partial refunds now record cash/bank/cheque method, with migration of legacy returns; cash snapshot and movement register include cash partial refunds. Unknown legacy methods block verified closure.

## V50 — Integrity checks / فحوص سلامة الصندوق
- Cash close readiness flags multiple open sessions, invalid full refund methods and non-positive historical amounts.
- Database CHECK constraints prevent negative expenses and partial refunds; tests verify these constraints.
- 200 unit tests passed on Linux. Windows EXE and hardware tests remain outstanding.

## V51 — Running cash balance and safer export / الرصيد المتراكم
- CSV register includes a running balance in centimes after every cash movement.
- Export checks consistency between itemized movements and cash-close readiness snapshot.
- CSV is first written and synced to a temporary file, then published without overwriting an existing report; temporary files are cleaned on failure.
- Four regression tests added: 204 tests passed in Linux development environment.
- Linux test success is not a Windows hardware or installer certification. Legacy ambiguous payments and actual purchase-lot cost accounting remain unresolved.

## V52 — Cash closing history / سجل إغلاقات الصندوق
- `cash_history.py` provides admin-only historical cash session reporting and CSV export.
- Verifies that counted cash minus expected cash equals the stored variance for every closed session.
- Export refuses overwrites, writes and fsyncs a temporary CSV, and publishes atomically.
- Historical entries remain read-only; this is an audit aid, not certified accounting.

## V53 — Cash closing history integrity
- Rejects negative opening, expected or counted cash in historical reports.
- Rejects malformed timestamps and sessions closed before their opening time.
- Historical data is not silently changed; finance administrators must review errors.
- Does not constitute a complete accounting ledger or a tested Windows installer.


V54: Historical cash-session export detects overlapping session intervals and rejects corrupt histories. Three regression tests added.

## V55 — Contrôle d'intégrité des lignes de vente
- Refuse la clôture vérifiée lorsque des lignes de vente ont des quantités non positives, des prix négatifs ou des coûts négatifs, même si le total de facture est équilibré.
- Détecte les lignes orphelines sans facture correspondante, sans modifier les données.
- Les vérifications sont en lecture seule. Elles ne remplacent pas un grand livre comptable ni un test Windows réel.

## V56 — Contrôle des quantités retournées / مراقبة الكميات المرتجعة
- Détection des quantités retournées dépassant la quantité vendue, cumulées entre plusieurs retours partiels.
- Détection des lignes de retour liées à une autre vente et des retours partiels sans lignes.
- Quatre tests supplémentaires ; 224 tests exécutés avec succès sous Linux.
- Attention : kit de compilation Windows, pas un installateur Windows testé.

## V57 — Partial refund valuation integrity
- Read-only reconciliation compares each partial refund with the sum of returned quantities multiplied by original sale-line unit prices.
- Mismatches block verified cash closing; no historical rows are changed automatically.
- Four regression tests added (228 total passing in Linux environment).
- Important limitation: this strict check assumes no separately authorized refund adjustments or discounts. Such adjustments require a dedicated recorded field before commercial use.
- No Windows EXE/installer or physical hardware validation has been performed.

## V58 — مراجعة المرتجعات لفواتير قديمة
أصبح فحص إغلاق الصندوق يشمل المرتجعات التي تمت خلال الجلسة الحالية حتى إذا كانت الفاتورة الأصلية من جلسة سابقة. ويحسب مجموع المرتجعات عبر جميع الجلسات لكشف تجاوز الكمية أو القيمة الأصلية. أُضيف اختباران آليان للحالتين الصحيحة وغير الصحيحة. هذا الإصدار حزمة بناء Windows وليس ملف Setup.exe مختبراً.


## V59 — Paiements initiaux des achats / الدفعات الأولية للمشتريات
- اختيار cash/bank/cheque في شاشة شراء البضاعة.
- تسجيل وسيلة الدفع في قاعدة البيانات مع ترحيل آمن للسجلات القديمة إلى unknown.
- خصم الدفعات الأولية النقدية فقط من الصندوق وسجل الحركات.
- التحذير من الدفعات القديمة غير الموثقة، دون افتراض أنها نقدية.
- لا يزال برنامج Windows التنفيذي يحتاج إلى بناء واختبار فعلي.

## V60 — Purchase invoice integrity / سلامة فواتير الشراء
- Cash close readiness checks purchase header totals against line quantities and costs.
- Detects missing/orphan purchase lines and invalid legacy initial payment methods.
- Checks are read-only; no historical invoice is silently changed.


## V61 — تدقيق المخزون / Rapprochement des stocks
أضيفت وحدة inventory_reconciliation.py لمقارنة الكمية الحالية مع مجموع حركات stock_ledger لكل منتج، دون تعديل قاعدة البيانات. تستلزم صلاحية reports وتتيح تصدير الاختلافات إلى CSV دون استبدال ملف سابق. لم تُدمج بعد في الواجهة. اختلاف الرصيد لا يثبت سببه ولا يعالج تكلفة الدفعات الفعلية.


## V62 — Inventory audit UI / تدقيق المخزون
زر تدقيق المخزون وزر تصدير الفروقات CSV لحساب المدير فقط. التقرير للقراءة فقط ولا يصحح الكميات تلقائياً. لا يوجد ملف Windows EXE مختبر ضمن هذه الحزمة.


## V63 — Atomic stock audit CSV / تصدير آمن لتدقيق المخزون
- The stock reconciliation CSV is now written to a temporary file, flushed and synced, then atomically published without overwriting existing reports.
- Failed CSV serialization leaves no partial final report.
- Three new automated tests cover success, failure, and non-overwrite.
- Windows installer remains a build kit, not a tested setup executable.

## V64 — Sale cost provenance / تتبع مصدر تكلفة البيع
- Added read-only cost provenance checks and manager-only GUI controls, plus CSV export.
- Flags sale costs without a preceding purchase invoice, or differing from the latest purchase cost.
- **Warning:** latest purchase is not necessarily the lot sold; opening stock may have no invoice. This is diagnostic only, NOT FIFO/FEFO accounting or proof of profit accuracy.
- Windows installer remains unbuilt and untested.

## V65 — FEFO lot allocation integrity / تدقيق دفعات المخزون
- Added `lot_allocation_audit.py` for read-only checks of tracked FEFO lots: received vs allocated vs remaining, product stock, missing allocations, and cross-product allocation links.
- Added admin-only GUI audit and CSV export controls.
- Six new automated tests; 271 tests pass in this build environment.
- This does **not** implement lot-specific purchase costs, accounting-grade profit, or a tested Windows installer.

## V66 — Explicit lot acquisition costs / تكلفة الدفعات
- `lot_costing.py`: immutable per-lot cost recording with invoice reference; read-only allocation-cost report.
- Missing historical costs remain UNKNOWN, never silently substituted with product master cost.
- Costs are entered through Python API only; GUI and actual profit integration remain pending.
- Does not claim audited profit or Windows installer readiness.


## V67 — GUI for FEFO lot acquisition costs / إدخال تكلفة الدفعات
- Manager-only lot cost entry in Lots/Péremption: lot ID, unit cost (DH), invoice reference.
- A manager-only read-only summary displays known and unknown costed quantities and known cost of FEFO sale allocations.
- Existing immutable lot-cost API is reused; no cost estimates for unknown lots.
- These figures do not replace the daily/weekly/monthly profit reports yet. Windows installer remains unbuilt and untested.


## V68 — Couverture mensuelle des coûts / تغطية تكاليف الشهر
أضيف تقرير للمدير يقارن جميع الوحدات المبيعة مع تخصيصات الدفعات وتكاليفها الموثقة، ويكشف الوحدات غير المخصصة والتخصيص الزائد والتكلفة المجهولة. التقرير تشخيصي فقط، ولا يحتسب المرتجعات أو يحل محل تقرير الأرباح المحاسبي.


V69: Added sales-only verified FEFO gross margin for monthly period; displays no margin if lot cost coverage incomplete. Excludes returns, expenses and discounts; not an accounting net profit. Five new tests.


## V70 — Verified FEFO period net result / صافي الربح
Added `verified_period_profit` and a manager UI button for monthly FEFO-based net profit including documented full/partial refunds and expenses. A partially returned line allocated across mixed-cost lots is explicitly marked **unverified** rather than assigning an invented cost. The result is only verifiable to the extent historical allocations and payment/expense records are complete; it is not a certified accounting statement. Windows EXE remains untested.

## V71 — Return overlap safety
- Verified FEFO period profit now refuses to certify a report when a full return and a partial return overlap on the same original sale line within the reporting period.
- Prevents double counting of returned cost and emits an explicit issue for investigation.
- Adds two regression tests (`tests/test_v71_return_overlap.py`).
- This remains a development build kit; Windows Setup.exe and full accounting reconciliation are not yet validated.

## V72 — Cross-period return validation / مراقبة المرتجعات بين الفترات
- `verified_period_profit` checks historical full/partial return overlap across reporting periods.
- Detects cumulative partial-return quantities exceeding original sold quantities.
- When inconsistent, `complete=False` and `net_profit_cents=None` (never publishes unverified profit).
- Added `tests/test_v72_cross_period_returns.py`.
- This is a source/build kit, NOT a tested standalone Windows installer.


## V73
- Résultat FEFO vérifié pour jour/semaine/mois, selon la date et le fuseau Africa/Casablanca.
- État non vérifié si les coûts sont incomplets, sans présenter de bénéfice certain.
- Invalidation du résultat lors du changement de date/période.
- Tests statiques de câblage GUI; exécution Windows non validée.

## V75 — Partial refund itemization safety
- Verified FEFO profit refuses to certify a partial refund without itemized returned quantities.
- Detects return details referencing missing or different original sale lines.
- Added two regression tests. The source/build kit is not a tested Windows installer.


## V76 — Export FEFO des profits vérifiés
Le bouton « تصدير FEFO CSV / Exporter » exporte le résultat de la période choisie avec état VERIFIED ou UNVERIFIED, motifs d’incertitude, montants en centimes et limites UTC. Export réservé aux comptes autorisés, sans écrasement de fichier existant. Les données incomplètes ne produisent jamais de profit net certifié.

## V77 — SQLite connection lifecycle
Temporary SQLite connections used by backup verification, diagnostics, offline recovery, release checks and recovery tests are now explicitly closed via `contextlib.closing`. This reduces unclosed-connection warnings and prevents lingering database file handles. The long-lived POS connection remains explicitly managed through `store.close()`. All 322 tests and release check passed in the development environment. Windows installer testing is still outstanding.


## V78 — CSV spreadsheet safety
- All exported verified-profit CSV values are escaped if they could be interpreted as formulas by spreadsheet software (=, +, -, @, including leading whitespace).
- Added regression tests for dangerous and safe values.
- This is a source/build kit, not a tested Windows Setup.exe.

## V79 — Windows build hardening
- The Windows build script now accepts `py -3` or `python` and validates Python >=3.10.
- The build runs the offline release gate before packaging.
- Inno Setup 6 is found via PATH or standard installation folders.
- A failed Inno Setup invocation now fails the build; the generated Setup.exe path is verified.
- If Inno Setup is absent, the build explicitly states that no installer was created.
- This source bundle is **not** a tested Windows installer. Test on Windows before deployment.


## V80 — Windows installer release gate
- Full test suite now runs before PyInstaller packaging.
- Old dist/ and installer_output/ folders are removed to prevent stale binaries being mistaken for new output.
- Inno Setup 6 is mandatory: missing installer compiler now fails the build.
- `verify_windows_build.py` checks that both EXEs and Setup.exe exist, have a nontrivial size and start with the Windows MZ signature. This is only a structural check, not an execution or security test.
- Real Windows installation, printing, barcode, restore and accounting acceptance tests remain outstanding.


## V81 — Release integrity / سلامة الإصدار
Windows build verification now checks PE/COFF structure instead of the MZ prefix alone, and creates `installer_output/build_manifest.json` with SHA-256 hashes and sizes for the two executables and installer. These checks do not establish Windows runtime compatibility or commercial readiness.

## V82 — Post-build integrity check / فحص سلامة ملفات التثبيت
After creating the SHA-256 manifest, the Windows build script independently rechecks the actual binaries against the saved manifest. Missing, changed, or unexpected files cause a build failure. This is not a Windows runtime test.
\n## V83 — Version consistency / توافق أرقام الإصدار\nFixed stale V80 application labels and V81 installer version in newer build kits. Windows build now fails if application and installer versions do not match V83. Three regression tests added. Windows runtime testing remains outstanding.\n
## V84 — Windows handoff / تسليم البناء على Windows
- Added `START_HERE_WINDOWS.bat` for a guided one-click build on a Windows build PC.
- Added `FINAL_WINDOWS_STEPS_AR.txt` with explicit deployment and acceptance-test instructions.
- Aligned app title and Inno Setup version with V84.
- No native Windows installer was produced or validated in this Linux environment.


## V85 — Windows acceptance
See `WINDOWS_ACCEPTANCE_AR.md` for the required on-device acceptance checklist. Passing automated tests is not Windows certification.


## V86 — standalone Windows installer via cloud build
See `WINDOWS_CLOUD_BUILD_AR.md` and `.github/workflows/windows-release.yml`. This package does not include a prebuilt Setup.exe.


## V87 — نسخة محمولة بدون تثبيت على حاسوب المحل
بعد تنفيذ BUILD_ON_WINDOWS.bat بنجاح على حاسوب بناء Windows، ينتج ملف `installer_output/EpicerieEnterprise_Portable_Win10_x64.zip` إلى جانب ملف Setup.exe. فك الضغط على Windows 10 64-bit وشغّل `START_EPICERIE.bat`. لا يحتاج حاسوب المحل إلى Python أو Inno Setup. **هذه الحزمة المصدرية لا تحتوي ملفات EXE بعد**، ويجب إجراء بناء Windows واختبارات قبول حقيقية قبل الاستخدام التجاري.

## V91 — بناء نسخة محمولة دون Inno Setup أو GitHub
على حاسوب إعداد Windows 10 x64 فقط، شغّل `BUILD_PORTABLE_ONLY_WINDOWS.bat` بعد تثبيت Python. ينتج ملف ZIP محمولًا يحتوي على EXE دون الحاجة إلى Python أو Inno Setup على حاسوب المحل. لم يتم تنفيذ بناء Windows أو اختبار الطباعة والباركود فعليًا هنا.

## V91 — Portable integrity gate
The portable Windows build now embeds SHA256_MANIFEST.json and checks the archive contents and Windows MZ executable headers before declaring the build successful. These checks do not substitute for running the executable on Windows 10 x64. No compiled EXE is included in this source buildkit.


## V91 - Windows packaged executable smoke gate
Before packaging, the Windows build runs `EpicerieEnterprise.exe --self-test <result-file>` against a temporary SQLite database. A PASS marker is required; failed smoke tests stop the build. This is a packaged-executable test, **not** a substitute for manual printer/barcode acceptance on Windows 10.

## V91 — Windows x64 portable validation
- Portable package now rejects fake MZ-only files and 32-bit PE executables.
- Both packaged executables must have valid AMD64 PE headers.
- 375 unit tests passed in the development environment; this is not a Windows runtime test.
- No Windows EXE or Setup.exe is included in this source/build kit.

## V97 — Windows 10 x64 build guard
- Portable ZIP includes EpicerieEnterprise.exe for direct double-click launch after successful Windows build.
- Build refuses 32-bit Python to avoid incompatible Windows executable output.
- No Windows executable has been built or tested in this Linux environment.

## V97 — اختبار الحزمة المحمولة بعد فك الضغط
- أضيف `portable_acceptance.py` لاختبار الملف التنفيذي الموجود داخل ZIP بعد فكّه في مجلد مؤقت على Windows.
- ترفض أداتا البناء تسليم الحزمة المحمولة إذا فشل الاختبار أو غابت علامة PASS.
- اجتازت الشيفرة 385 اختباراً في بيئة التطوير؛ لا يعني ذلك اختبار EXE على Windows.
- حاسوب المحل لا يحتاج Python بعد إنتاج النسخة المحمولة فعلياً.
