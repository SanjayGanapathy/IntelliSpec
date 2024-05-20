const int analogPin = A0;  // Analog pin connected to the photodiode circuit
const float Vref = 5.0;    // Reference voltage of the Arduino (change to 3.3 if using 3.3V)
const int numReadings = 300;
const int stabilizationTime = 10000;   // Stabilization time in milliseconds (10 seconds)
const int loadSampleTime = 3000;       // Time to load the sample in milliseconds (3 seconds)
const int waitAfterSampleTime = 5000;  // Time to wait after loading the sample in milliseconds (5 seconds)

void setup() {
  Serial.begin(9600);  // Start serial communication at 9600 baud
}

void loop() {
  int initialReadings[numReadings];  // Array to store initial readings
  int medianReading;                 // Median of initial readings
  float initialVoltage;              // Initial voltage
  float voltage;                     // Current voltage
  int sensorValue;                   // Current sensor value
  float absorbance1;                  // Calculated absorbance
  float absorbance2;

  // Collect initial readings
  for (int i = 0; i < numReadings; i++) {
    initialReadings[i] = analogRead(analogPin);
    delay(50);  // Delay between readings
  }

  // Calculate median of initial readings
  medianReading = median(initialReadings, numReadings);
  initialVoltage = (float)medianReading / 1023.0 * Vref;

  // Print calibration end and initial voltage
  Serial.print("Calibration period ends. Initial Voltage: ");
  Serial.println(initialVoltage, 3);  // Print initial voltage with 3 decimal places

  // Wait for stabilization
  delay(stabilizationTime);

  // Load the sample
  delay(loadSampleTime);

  // Wait after loading the sample
  delay(waitAfterSampleTime);

  // Collect second reading
  sensorValue = analogRead(analogPin);
  voltage = (float)sensorValue / 1023.0 * Vref;

  //Calculate absorbance (Aaryan's phone)
  absorbance1 = log10(((initialVoltage-0.005)/(voltage-0.005)));
  absorbance2 = log10(((initialVoltage*100/99)/(voltage+(initialVoltage*1/99))));
  

  // Print final voltage and absorbance
  Serial.print("Final Voltage: ");
  Serial.println(voltage, 3);  // Print second voltage with 3 decimal places
  Serial.print("Absorbance 1.0: ");
  Serial.println(absorbance1, 3);
  Serial.print("Absorbance 2.0: ");
  Serial.println(absorbance2, 3);  // Print absorbance with 3 decimal places

  delay(1000);  // Wait for 1 second before repeating the loop
}

// Function to calculate the median of an array
int median(int readings[], int n) {
  int temp;
  // Sort the array
  for (int i = 0; i < n - 1; i++) {
    for (int j = 0; j < n - i - 1; j++) {
      if (readings[j] > readings[j + 1]) {
        temp = readings[j];
        readings[j] = readings[j + 1];
        readings[j + 1] = temp;
      }
    }
  }
  // Calculate median
  if (n % 2 == 0) {
    return (readings[n / 2] + readings[n / 2 - 1]) / 2;
  } else {
    return readings[n / 2];
  }
}