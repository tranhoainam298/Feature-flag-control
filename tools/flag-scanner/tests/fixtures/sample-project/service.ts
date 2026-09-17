// Sample TypeScript file with FlagOps calls and comments
// Do not match: client.isEnabled("commented-flag-key")

export class FeatureService {
  constructor(private client: any, private openfeatureClient: any) {}

  public async checkFeatures(): Promise<void> {
    // Calling checkout-v2
    const isV2 = await this.client.isEnabled("checkout-v2");

    /* Multi-line comment
       openfeatureClient.getBooleanValue("multi-line-commented-flag", false);
    */
    const isDark = await this.openfeatureClient.getBooleanValue("dark-mode", false);

    const paymentVariant = this.client.getStringValue("payment-v2", "stripe");

    // String that is not a method call
    const decoy = "dark-mode";
  }
}
