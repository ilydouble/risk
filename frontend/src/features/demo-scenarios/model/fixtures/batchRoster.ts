// Sample roster used to demonstrate the batch evaluation flow without a real file.
// First column is the company name; remaining columns are informational only.
export const sampleRosterCsv = [
  "企业名称,统一社会信用代码/注册号,来源,备注",
  "北辰精密制造有限公司,91310000MA1FL2X309,核心供应商名单,年度复核",
  "莱茵新能源科技股份有限公司,DE-HRB-8841209,欧洲区拓展,新增授信申请",
  "森田通商株式会社,JP-2011-0039281,东亚贸易批次,账期调整",
  "安第斯矿业资源集团,CL-RUT-96.184.220-7,大宗贸易批次,重点关注",
  "恒信远东供应链有限公司,HK-2278431,跨境供应链批次,重点关注",
  "南十字星物流私人有限公司,SG-201804123K,东南亚物流批次,续授信",
  "奥罗拉生物医药有限公司,US-DE-6420118,创新药批次,新增授信申请",
  "新月工程承包股份有限公司,VN-0108347761,东南亚基建批次,存量客户",
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
  "Andes Mining Resources Group S.A.,CL-RUT-96.184.220-7,Bulk trade batch,Watchlist",
  "Hengxin Far East Supply Chain Ltd.,HK-2278431,Cross-border supply chain batch,Watchlist",
  "Southern Cross Logistics Pte. Ltd.,SG-201804123K,Southeast Asia logistics batch,Credit renewal",
  '"Aurora BioPharma, Inc.",US-DE-6420118,Biopharma batch,New credit request',
  "Crescent Engineering Contracting JSC,VN-0108347761,Southeast Asia infrastructure batch,Existing client",
  "Dawn Supply Chain Management (Suzhou) Ltd.,91320500MA1Q4X7L21,East China batch,Pending onboarding",
  "Polaris Precision Manufacturing Ltd.,91310000MA1FL2X309,Core supplier list,Duplicate submission",
  "Blue Ocean Logistics LLC,US-NV-20193388201,Americas batch,Pending onboarding",
].join("\n");
