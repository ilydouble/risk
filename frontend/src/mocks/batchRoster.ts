// Sample roster used to demonstrate the batch evaluation flow without a real file.
// First column is the company name; remaining columns are informational only.
export const sampleRosterCsv = [
  "企业名称,统一社会信用代码/注册号,来源,备注",
  "北辰精密制造有限公司,91310000MA1FL2X309,核心供应商名单,年度复核",
  "莱茵新能源科技股份有限公司,DE-HRB-8841209,欧洲区拓展,新增授信申请",
  "森田通商株式会社,JP-2011-0039281,东亚贸易批次,账期调整",
  "恒信远东供应链有限公司,HK-2278431,跨境供应链批次,重点关注",
  "新月工程承包股份有限公司,VN-0108347761,东南亚基建批次,存量客户",
  "达尼洛纺织进出口公司,IT-MI-2019344882,欧洲区拓展,风险预警",
  "诺曼底港口物流集团,FR-RCS-812009431,欧洲区拓展,续授信",
  "西伯利亚木材工贸有限公司,RU-INN-7703418290,大宗贸易批次,重点关注",
  "墨尔本医疗器械有限公司,AU-ACN-618274019,亚太区批次,新增客户",
  "伊斯坦布尔建材贸易公司,TR-MERSIS-0628471,中东批次,风险预警",
  "斯德哥尔摩清洁能源公司,SE-BOLAG-556710-2841,欧洲区拓展,优质客户",
  "赫尔辛基通信技术有限公司,FI-BUSINESS-ID-2846119-4,北欧科技批次,新增授信申请",
  "蒙特雷汽车零部件有限公司,MX-RFC-MAP180912HH8,北美供应链批次,续授信",
  "拉各斯建材进出口公司,NG-RC-1428390,非洲批次,高风险名单",
  "晨曦供应链管理（苏州）有限公司,91320500MA1Q4X7L21,华东批次,待建档",
  "北辰精密制造有限公司,91310000MA1FL2X309,核心供应商名单,重复提交",
  "Blue Ocean Logistics LLC,US-NV-20193388201,美洲批次,待建档",
].join("\n");

// English counterpart of the sample roster, used when the site language is English.
export const sampleRosterCsvEn = [
  "Company Name,Registration No / Credit Code,Source,Note",
  "Polaris Precision Manufacturing Ltd.,91310000MA1FL2X309,Core supplier list,Annual review",
  "Rhein New Energy Technology AG,DE-HRB-8841209,Europe expansion,New credit request",
  '"Morita Trading Co., Ltd.",JP-2011-0039281,East Asia trade batch,Payment term adjustment',
  "Hengxin Far East Supply Chain Ltd.,HK-2278431,Cross-border supply chain batch,Watchlist",
  "Crescent Engineering Contracting JSC,VN-0108347761,Southeast Asia infrastructure batch,Existing client",
  "Danilo Textile Import & Export S.p.A.,IT-MI-2019344882,Europe expansion,Risk alert",
  "Normandie Port Logistics Group SAS,FR-RCS-812009431,Europe expansion,Credit renewal",
  "Siberia Timber Industry LLC,RU-INN-7703418290,Bulk trade batch,Watchlist",
  "Melbourne Medical Devices Pty Ltd,AU-ACN-618274019,APAC batch,New client",
  "Istanbul Building Materials Trading A.Ş.,TR-MERSIS-0628471,Middle East batch,Risk alert",
  "Stockholm Clean Energy AB,SE-BOLAG-556710-2841,Europe expansion,Prime client",
  "Helsinki Communications Technology Oy,FI-BUSINESS-ID-2846119-4,Nordic tech batch,New credit request",
  "Monterrey Auto Parts S. de R.L. de C.V.,MX-RFC-MAP180912HH8,North America supply chain batch,Credit renewal",
  "Lagos Building Materials Import & Export Ltd,NG-RC-1428390,Africa batch,High-risk list",
  "Dawn Supply Chain Management (Suzhou) Ltd.,91320500MA1Q4X7L21,East China batch,Pending onboarding",
  "Polaris Precision Manufacturing Ltd.,91310000MA1FL2X309,Core supplier list,Duplicate submission",
  "Blue Ocean Logistics LLC,US-NV-20193388201,Americas batch,Pending onboarding",
].join("\n");